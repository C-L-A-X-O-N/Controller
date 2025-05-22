import os, master, node
import logging
logger = logging.getLogger(__name__)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    broker_host = os.environ.get("BROKER_HOST", "localhost")
    broker_port = int(os.environ.get("BROKER_PORT", 1883))

    if os.environ.get("MASTER", "False") == "True":
        logger.info("Running as master")
        master.main(host=broker_host, port=broker_port)
    else:
        logger.info("Running as node")
        node.main(host=broker_host, port=broker_port)

    logging.shutdown()