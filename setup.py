from setuptools import setup, find_packages

setup(
    name="trading_consumer",
    version="0.1.1",
    description="Independent trading consumer that reads Telegram messages and executes trades on Hyperliquid",
    author="Trading Bot",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "python-telegram-bot>=20.0",
        "ccxt>=4.0.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0",
        "asyncio-mqtt>=0.13.0",
        "aiofiles>=23.0.0",
        "httpx>=0.25.0",
        "tenacity>=8.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "trading-consumer=trading_consumer.main:main",
        ],
    },
) 