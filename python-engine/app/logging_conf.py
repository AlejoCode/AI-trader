import json, logging, os, sys
from logging.handlers import RotatingFileHandler

def setup_logging(log_dir: str, level="INFO", json_format=True, rotate_mb=50, keep=7):
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "engine.log")
    handler = RotatingFileHandler(log_path, maxBytes=rotate_mb*1024*1024, backupCount=keep)
    stream = logging.StreamHandler(sys.stdout)

    class JsonFormatter(logging.Formatter):
        def format(self, record):
            base = {
                "level": record.levelname,
                "ts": self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S.%f"),
                "msg": record.getMessage(),
                "logger": record.name,
            }
            if record.args and isinstance(record.args, dict):
                base.update(record.args)
            return json.dumps(base, ensure_ascii=False)
    fmt = JsonFormatter() if json_format else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt); stream.setFormatter(fmt)
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler, stream])
