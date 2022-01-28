from trade.utility import TEMP_DIR


class ChanLog:

    @staticmethod
    def log(freq, symbol, data) -> None:
        data = str(data)
        if len(data) <= 0:
            return
        chan_path = TEMP_DIR.joinpath('chan_log')
        if not chan_path.exists():
            chan_path.mkdir(parents=True)
        chan_file = chan_path.joinpath(symbol + '-' + freq + '.txt')
        with open(chan_file, 'a') as f:
            f.write(data + '\n')
