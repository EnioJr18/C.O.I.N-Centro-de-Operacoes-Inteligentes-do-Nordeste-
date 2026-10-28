import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from channels_redis.core import RedisChannelLayer


TIMEOUT_SECONDS = 12


def make_layer(redis_url, prefix):
    return RedisChannelLayer(
        hosts=[redis_url],
        prefix=prefix,
        expiry=30,
        group_expiry=60,
    )


async def close_layer(layer):
    await layer.close_pools()


async def publish_from_subprocess():
    redis_url = os.environ['COIN_REDIS_SMOKE_URL']
    prefix = os.environ['COIN_REDIS_SMOKE_PREFIX']
    group = os.environ['COIN_REDIS_SMOKE_GROUP']
    event_id = os.environ['COIN_REDIS_SMOKE_EVENT_ID']
    layer = make_layer(redis_url, prefix)
    try:
        await layer.group_send(
            group,
            {
                'type': 'smoke.message',
                'event_id': event_id,
                'source': 'subprocess',
            },
        )
    finally:
        await close_layer(layer)


async def run_smoke_test():
    redis_url = os.environ.get('REDIS_URL', '').strip()
    if not redis_url:
        raise RuntimeError('REDIS_URL ausente para o smoke test.')

    identifier = uuid4().hex
    prefix = f'coin-smoke-{identifier}'
    group = f'coin.redis.smoke.{identifier}'
    event_id = str(uuid4())
    layer = make_layer(redis_url, prefix)
    channel = await layer.new_channel('coin.redis.smoke')
    joined = False
    try:
        await asyncio.wait_for(layer.group_add(group, channel), TIMEOUT_SECONDS)
        joined = True
        environment = os.environ.copy()
        environment.update(
            {
                'COIN_REDIS_SMOKE_URL': redis_url,
                'COIN_REDIS_SMOKE_PREFIX': prefix,
                'COIN_REDIS_SMOKE_GROUP': group,
                'COIN_REDIS_SMOKE_EVENT_ID': event_id,
            }
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(Path(__file__).resolve()),
            '--publish',
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), TIMEOUT_SECONDS)
        if process.returncode != 0:
            raise RuntimeError('O subprocesso de publicação Redis falhou.')

        message = await asyncio.wait_for(layer.receive(channel), TIMEOUT_SECONDS)
        expected = {
            'type': 'smoke.message',
            'event_id': event_id,
            'source': 'subprocess',
        }
        if message != expected:
            raise RuntimeError('A mensagem Redis recebida não corresponde ao contrato esperado.')
    finally:
        if joined:
            try:
                await layer.group_discard(group, channel)
            except Exception:
                pass
        await close_layer(layer)


def main():
    parser = argparse.ArgumentParser(description='Valida o channel layer Redis entre processos.')
    parser.add_argument('--publish', action='store_true', help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    try:
        asyncio.run(publish_from_subprocess() if arguments.publish else run_smoke_test())
    except Exception as exc:
        print(f'Redis multiprocess smoke test: FAIL ({type(exc).__name__})', file=sys.stderr)
        raise SystemExit(1) from None
    if not arguments.publish:
        print('Redis multiprocess smoke test: OK')


if __name__ == '__main__':
    main()
