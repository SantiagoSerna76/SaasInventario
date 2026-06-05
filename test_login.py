import asyncio
from main import login
from fastapi.security import OAuth2PasswordRequestForm
import traceback

async def main():
    try:
        form = OAuth2PasswordRequestForm(username='admin@la14.com', password='123456', scope='', client_id='', client_secret='')
        result = await login(form)
        print("Success:", result)
    except Exception as e:
        print("Error:")
        traceback.print_exc()

asyncio.run(main())
