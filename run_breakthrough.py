import asyncio
import aiohttp
import ccxt.async as ccxt
import time
from datetime import datetime, timedelta
import pandas as pd
import logging

def setup_logger(name, log_file, level=logging.INFO):
    """Function setup as many loggers as you want"""

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    # add the handlers to logger

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger

participants = ['binance', 'bitfinex', 'bittrex', 'huobi']
existance = {}
loggers = {}
for ex in participants:
    existance[ex] = []
    loggers[ex] = setup_logger('%s' % ex, '%s.log' % ex)

fees = {'binance':0.05/100,
        'bitfinex':0.1/100,
        'bittrex':0.25/100,
        'huobi':0.04/100
        }

exs = {'binance':ccxt.binance(),
       'bitfinex':ccxt.bitfinex(),
       'bittrex':ccxt.bittrex(),
       'huobi':ccxt.huobipro()}

datas = {}
universe = pd.read_excel('binance/backtest_fee0.2&volumefilter.xlsx')
loop = asyncio.get_event_loop()

k = 0.5
target_vol = 0.25
fee = 0.2 / 100
window = 500
min_volume = {'USDT': 5000000, 'BTC': 500, 'ETH': 10000, 'BNB':500000}
pairs = []
info = {}

pairs.append(['BTC', 'USDT'])
pairs.append(['LTC', 'USDT'])
pairs.append(['ETH', 'USDT'])
pairs.append(['NEO', 'USDT'])
pairs.append(['BNB', 'USDT'])

async def checkspread(base, quote, exchange):
    if exchange == 'bitfinex':
        quote = 'USD'

    while True:
        await asyncio.sleep(0.5)
        res = await exs[exchange].fetch_order_book(symbol='%s/%s' % (base,quote))
        bidprice = res['bids'][0][0]
        askprice = res['asks'][0][0]
        spread = (askprice - bidprice) / bidprice
        loggers[exchange].info('%s %s %s %s' % (base, quote, exchange, spread))

async def getprice(base, quote, exchange):
    if exchange == 'bitfinex':
        quote = 'USD'
    res = await exs[exchange].fetch_order_book(symbol='%s/%s' % (base,quote))
    datas[exchange] = [res['bids'][0][0] * (1-fees[exchange]), res['bids'][0][1], res['asks'][0][0] * (1+fees[exchange]), res['asks'][0][1]]

async def gethist(base, quote):
    info['%s/%s' % (base, quote)] = []
    rawdata = await exs['binance'].fetch_ohlcv(symbol='%s/%s' % (base, quote), timeframe='1d')
    rawdata.reverse()
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    two = (now - timedelta(days=2)).strftime('%Y-%m-%d')
    three = (now - timedelta(days=3)).strftime('%Y-%m-%d')
    four = (now - timedelta(days=4)).strftime('%Y-%m-%d')
    five = (now - timedelta(days=5)).strftime('%Y-%m-%d')
    nowDatetime = now.strftime('%Y-%m-%d %H:%M:%S')
    mean = []

    for data in rawdata:
        ts = data[0] / 1000
        open = data[1]
        high = data[2]
        low = data[3]
        close = data[4]
        volume = data[5]
        time = datetime.fromtimestamp(ts)
        date = time.strftime('%Y-%m-%d')
        if date == now.strftime('%Y-%m-%d'):
            info['%s/%s' % (base, quote)].append(open)
            info['%s/%s' % (base, quote)].append(high)


        elif date == yesterday.strftime('%Y-%m-%d'):
            range_yesterday = high - low
            vol = (range_yesterday * k ) / close * 100
            ratio = min(1, target_vol / vol)
            info['%s/%s' % (base, quote)].append(range_yesterday)
            info['%s/%s' % (base, quote)].append(ratio)

        elif date == two or date == three or date == four or date == five:
            mean.append(close)

    info['%s/%s' % (base, quote)].append(sum(mean)/len(mean))

    # today open, today high, range_yesterday, ratio, mean4를 첨가함


async def check(base, quote):

    while True:
        await asyncio.sleep(0.1)
        res = await exs['binance'].fetch_ticker(symbol='%s/%s' % (base,quote))
        nowprice = res['last']
        open = info['%s/%s' % (base, quote)][0]
        high = info['%s/%s' % (base, quote)][1]
        range_yesterday = info['%s/%s' % (base, quote)][2]
        ratio = info['%s/%s' % (base, quote)][3]
        mean4 = info['%s/%s' % (base, quote)][4]
        buyprice = open + k * range_yesterday

        if high > max(buyprice, mean4):
            print('opportunity already occured')

        if nowprice > max(buyprice, mean4):
            print('buy', base, quote, nowprice, buyprice)
            tasks = []
            for ex in participants:
                if [base, quote] in existance[ex]:
                    tasks.append(getprice(base, quote, ex))

            await asyncio.gather(*tasks)

            print(datas)

            # ask price 중에서 가장 싼걸로 사야지, 그리고 그거를 buyprice랑 비교

        else:
            print(base, quote, 'opportunity not yet')
            print(buyprice, nowprice)

async def run():

    for ex in participants:
        res = await exs[ex].fetch_markets()
        for data in res:
            for pair in pairs:
                base = data['base']
                quote = data['quote']
                if ex == 'bitfinex' and quote == 'USD':
                    quote = 'USDT'

                if base == pair[0] and quote == pair[1]:
                    existance[ex].append(pair)

    print(existance)

    tasks = []
    for ex in participants:
        base = 'BTC'
        quote = 'USDT'
        if [base, quote] in existance[ex]:
            tasks.append(checkspread(base, quote, ex))

    await asyncio.gather(*tasks)

    # tasks = []
    # for ex in participants:
    #     base = 'BTC'
    #     quote = 'USDT'
    #     if [base, quote] in existance[ex]:
    #         tasks.append(getprice(base, quote, ex))
    #
    # await asyncio.gather(*tasks)
    #
    # df = pd.DataFrame.from_dict(datas, orient='index')
    # df.columns = ['sellprice', 'sellvolume', 'buyprice', 'buyvolume']
    # #살때
    # df.sort_values(by = ['buyprice'], inplace=True, ascending=True)
    # print(df)
    # #print(df.index[0])
    #
    # #팔때
    # df.sort_values(by = ['sellprice'], inplace=True, ascending=False)
    # print(df)

    # tasks = []
    # for pair in pairs:
    #     tasks.append(gethist(pair[0], pair[1]))
    #
    # await asyncio.gather(*tasks)
    #
    # print(info)
    #
    # tasks = []
    # for pair in pairs:
    #     tasks.append(check(pair[0], pair[1]))
    #
    # await asyncio.gather(*tasks)

loop.run_until_complete(run())


