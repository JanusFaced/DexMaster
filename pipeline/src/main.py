import os
import sys
import time
import psycopg2
from psycopg2 import OperationalError
from web3 import Web3

ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"

ARBITRUM_ASSETS = {
    "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
    "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    "CAKE": "0x1b896893dfc86bb67Cf57767298b9073D2c1bA2c",
    "1INCH": "0x6314c31a7a1652ce482cffe247e9cb7c3f4bb9af",
    "LINK": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4",
    "UNI": "0xFa7F8980b0f1E64A2062791cc3b0871572f1F7f0",
    "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
    "SUSHI": "0xd4d42f0b6def4ce0383636770ef773390d85c61a",
    
    "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
}

DEXES = {
    "uniswap_v3": {
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "fees": [500, 3000, 10000],
        "FACTORY_ABI": '[{"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"internalType":"address","name":"pool","type":"address"}],"stateMutability":"view","type":"function"}]',
        "POOL_ABI": '[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}]',
    },
    "sushiswap_v3": {
        "factory": "0x1af415a1EbA07a4986a52B6f2e7dE7003D82231e",
        "fees": [500, 3000, 10000],
        "FACTORY_ABI": '[{"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"internalType":"address","name":"pool","type":"address"}],"stateMutability":"view","type":"function"}]',
        "POOL_ABI": '[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}]',
    },
    "pancakeswap_v3": {
        "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
        "fees": [100, 500, 2500, 10000],
        "FACTORY_ABI": '[{"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"internalType":"address","name":"pool","type":"address"}],"stateMutability":"view","type":"function"}]',
        "POOL_ABI": '[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint32","name":"feeProtocol","type":"uint32"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}]',
    },
}

ERC20_DECIMALS_ABI = '[{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]'

def get_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
    )

def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            conn = get_conn()
            conn.close()
            print(f"[+] Connected to DB on attempt {attempt}")
            return
        
        except OperationalError as e:
            print(f"[-] Attempt {attempt}/{retries}: {e}")
            time.sleep(delay)
    
    print("[!] Could not connect to DB, giving up")
    sys.exit(1)

def connect_to(RPC):
    web3_connect = Web3(Web3.HTTPProvider(RPC))

    if web3_connect.is_connected():
        print(f"[+] Open connet with {RPC}!")
    
    else:
        print(f"[-] Connection failed with {RPC}...")

    return web3_connect

def get_decimals(web3_connect, token):

    contract = web3_connect.eth.contract(
        address=Web3.to_checksum_address(token),
        abi=ERC20_DECIMALS_ABI,
    )
    decimals = contract.functions.decimals().call()

    return decimals

def get_pool_price(
        web3_connect,
        factory_addr,
        numerator,
        denominator,
        fee,
        FACTORY_ABI,
        POOL_ABI,
    ) -> float:
    
    token_a = ARBITRUM_ASSETS[numerator]
    token_b = ARBITRUM_ASSETS[denominator]

    factory = web3_connect.eth.contract(address=Web3.to_checksum_address(factory_addr), abi=FACTORY_ABI)

    try:
        pool_addr = factory.functions.getPool(
            Web3.to_checksum_address(token_a),
            Web3.to_checksum_address(token_b),
            fee
        ).call()
    
    except Exception as e:
        print(f"pool_addr ERROR: {e}")
        return None
    
    if pool_addr == "0x0000000000000000000000000000000000000000":
        return "zero"
    
    pool = web3_connect.eth.contract(address=Web3.to_checksum_address(pool_addr), abi=POOL_ABI)

    try:
        slot0 = pool.functions.slot0().call()
        sqrt_price_x96 = slot0[0]
    
    except Exception as e:
        print(f"slot0 ERROR: {e}")
        return None
    
    if sqrt_price_x96 == 0:
        print(f"sqrt_price_x96 = {sqrt_price_x96}")
        return None
    
    price_raw = (sqrt_price_x96 / (2**96)) ** 2

    decimals_token_a = get_decimals(web3_connect, token_a)
    decimals_token_b = get_decimals(web3_connect, token_b)

    token0_is_a = int(token_a, 16) < int(token_b, 16)

    if token0_is_a:
        price = price_raw * (10**decimals_token_a) / (10**decimals_token_b)
    else:
        price = (1 / price_raw) * (10**decimals_token_a) / (10**decimals_token_b)
    
    return price

def main() -> None:
    wait_for_db()

    database_connect = get_conn()
    database_cursor = database_connect.cursor()

    web3_connect = connect_to(RPC=ARBITRUM_RPC)

    CHAIN_ID = web3_connect.eth.chain_id

    assets_list = [
        "WBTC",
        "WETH",
        "UNI",
        "SUSHI",
        "CAKE",
        "LINK",
        "ARB",
        "1INCH",
    ]

    denominator_name = 'USDC'

    while True:

        for dex_name, config in DEXES.items():
            print(f" > dex_name: {dex_name}")
            
            for asset_name in assets_list:
                
                for fee in config["fees"]:
                    price = get_pool_price(
                        web3_connect=web3_connect,
                        factory_addr=config["factory"],
                        numerator=asset_name,
                        denominator=denominator_name,
                        fee=fee,
                        FACTORY_ABI=config["FACTORY_ABI"],
                        POOL_ABI=config["POOL_ABI"],
                    )

                    if price != "zero":
                        fee_pct = fee / 10000
                        print(f" <> pool -> [ asset: {asset_name:<5} | fee: {fee_pct:<6.2f}% ] -> price = {price:<20.7f} {denominator_name}")

        print("\n[*] Готово. Ожидание 60 секунд...")
        time.sleep(60)

    database_cursor.close()
    database_connect.close()

if __name__ == "__main__":
    main()