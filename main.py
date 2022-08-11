import asyncio
import datetime
import os
import httpx

from fastapi import FastAPI
from database import Base, engine, Queries, Groups, SessionLocal

# Ограничение запросов, выполняемых параллельно, чтобы VK API не блокировалось
MAX_IN_PARALLEL = 3
limit_sem = asyncio.Semaphore(MAX_IN_PARALLEL)

app = FastAPI()

# Получение токена и версии VK API
vk_token = os.getenv('VK_TOKEN')
vk_api_version = os.getenv('VK_API_VERSION')


# Инициализация базы данных
def init_db():
    Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def on_startup():
    init_db()


# Функция отправки запроса к VK API
async def request(client, url):
    async with limit_sem:
        await asyncio.sleep(1)
        response = await client.get(url)
        if 'response' in response.json() and 'items' in response.json()['response']:
            return response.json()['response']['items']
        else:
            return []


# Функция получения id групп друзей и пользователя
async def groups_id(user_id, find_friends=False):
    friend_list_url = 'https://api.vk.com/method/friends.get?user_id={}&access_token={}&v={}'.format(user_id, vk_token,
                                                                                                     vk_api_version)
    user_group_list = 'https://api.vk.com/method/groups.get?user_id={}&access_token={}&v={}'.format(user_id, vk_token,
                                                                                                    vk_api_version)
    result = []
    async with httpx.AsyncClient() as client:
        if find_friends:
            resp = await client.get(friend_list_url)

            friend_list = resp.json()['response']['items']
            tasks = [
                request(client, 'https://api.vk.com/method/groups.get?user_id={}&access_token={}&v={}'.
                        format(user, vk_token, vk_api_version))
                for user in friend_list]
            friends_group = await asyncio.gather(*tasks)
            result += [item for sublist in friends_group for item in sublist]
            await asyncio.sleep(1)
        response = await client.get(user_group_list)
        if 'response' in response.json() and 'items' in response.json()['response']:
            result += response.json()['response']['items']

    return result


# Функция поиска групп
async def find_groups(user_id, query, group_ids, save_db=False):
    url = 'https://api.vk.com/method/groups.search?q={}&access_token={}&v={}'.format(query, vk_token, vk_api_version)
    result = []
    db = SessionLocal()
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if save_db:
            new_query = Queries(
                query_date_time=datetime.datetime.now(),
                query=query,

            )
            db.add(new_query)
            db.commit()
            db.refresh(new_query)
        for item in response.json()['response']['items']:
            # Проверяется есть ли id группы в списке id групп пользователя или его друзей
            if item['id'] in group_ids:
                if save_db:
                    new_group = Groups(
                        name=item['name'],
                        screen_name=item['screen_name'],
                        is_closed=item['is_closed'],
                        type=item['type'],
                        query_id=new_query.id,
                        user_id=user_id,

                    )
                    db.add(new_group)
                    db.commit()
                    db.refresh(new_group)
                result.append({
                    'id': item['id'],
                    'name': item['name'],
                    'screen_name': item['screen_name'],
                    'is_closed': item['is_closed'],
                    'type': item['type'],
                })
    return result


# Эндпоинт для получения когда-либо найденных групп из базы данных
@app.get("/groups/list/{user_id}")
async def groups(user_id: int):
    db = SessionLocal()
    result = []
    for group in db.query(Groups).filter(Groups.user_id == user_id):
        result.append({
            'name': group.name,
            'screen_name': group.screen_name,
            'is_closed': group.is_closed,
            'type': group.type,
        })
    return result


# Эндпоинт для поиска групп (сообществ) по подстроке и (одновременно) в которые входит пользователь или его друзья.
@app.get("/groups/friends/{user_id}")
async def friends_groups(user_id: int, query: str, skip: int | None = 0, limit: int | None = 10):
    group_ids = await groups_id(user_id, True)
    result = await find_groups(user_id, query, group_ids, False)
    return result[skip: skip + limit]


# Эндпоинт для поиска групп (сообществ) по подстроке в которые входит пользователь
@app.get("/groups/{user_id}")
async def groups(user_id: int, query: str, skip: int | None = 0, limit: int | None = 10):
    group_ids = await groups_id(user_id, False)
    result = await find_groups(user_id, query, group_ids, True)
    return result[skip: skip + limit]
