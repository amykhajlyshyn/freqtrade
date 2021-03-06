# pragma pylint: disable=missing-docstring
import logging
import os

import pytest
import arrow
from pandas import DataFrame

from freqtrade import exchange
from freqtrade.analyze import analyze_ticker
from freqtrade.exchange import Bittrex
from freqtrade.main import should_sell
from freqtrade.persistence import Trade

logging.disable(logging.DEBUG)  # disable debug logs that slow backtesting a lot


def format_results(results):
    return 'Made {} buys. Average profit {:.2f}%. Total profit was {:.3f}. Average duration {:.1f} mins.'.format(
        len(results.index), results.profit.mean() * 100.0, results.profit.sum(), results.duration.mean() * 5)


def print_pair_results(pair, results):
    print('For currency {}:'.format(pair))
    print(format_results(results[results.currency == pair]))


def backtest(backtest_conf, backdata, mocker):
    trades = []
    exchange._API = Bittrex({'key': '', 'secret': ''})
    mocked_history = mocker.patch('freqtrade.analyze.get_ticker_history')
    mocker.patch.dict('freqtrade.main._CONF', backtest_conf)
    mocker.patch('arrow.utcnow', return_value=arrow.get('2017-08-20T14:50:00'))
    for pair, pair_data in backdata.items():
        mocked_history.return_value = pair_data
        ticker = analyze_ticker(pair)[['close', 'date', 'buy']].copy()
        # for each buy point
        for row in ticker[ticker.buy == 1].itertuples(index=True):
            trade = Trade(
                open_rate=row.close,
                open_date=row.date,
                amount=1,
                fee=exchange.get_fee() * 2
            )
            # calculate win/lose forwards from buy point
            for row2 in ticker[row.Index:].itertuples(index=True):
                if should_sell(trade, row2.close, row2.date):
                    current_profit = trade.calc_profit(row2.close)

                    trades.append((pair, current_profit, row2.Index - row.Index))
                    break
    labels = ['currency', 'profit', 'duration']
    results = DataFrame.from_records(trades, columns=labels)
    return results


@pytest.mark.skipif(not os.environ.get('BACKTEST', False), reason="BACKTEST not set")
def test_backtest(backtest_conf, backdata, mocker, report=True):
    results = backtest(backtest_conf, backdata, mocker)

    print('====================== BACKTESTING REPORT ================================')
    for pair in backdata:
        print_pair_results(pair, results)
    print('TOTAL OVER ALL TRADES:')
    print(format_results(results))
