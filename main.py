from trade.engine import MainEngine
from trade.ui import MainWindow, create_qapp


def main():
    qapp = create_qapp()
    main_engine = MainEngine()
    main_window = MainWindow(main_engine)
    main_window.showMaximized()
    qapp.exec()


if __name__ == "__main__":
    main()
