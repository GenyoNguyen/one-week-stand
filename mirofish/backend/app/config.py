"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
import shlex
from dotenv import load_dotenv

# 优先加载 MiroFish 自己的 .env；作为子目录运行时，回退到仓库根目录。
mirofish_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
env_file = os.environ.get('MIROFISH_ENV_FILE')
if not env_file:
    env_candidates = (
        os.path.join(mirofish_root, '.env'),
        os.path.join(os.path.dirname(mirofish_root), '.env'),
    )
    env_file = next((path for path in env_candidates if os.path.isfile(path)), None)

if env_file:
    load_dotenv(env_file, override=True)
else:
    # 没有配置文件时使用进程环境（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # Local MCP tools
    MCP_ENABLED = os.environ.get('MCP_ENABLED', 'true').lower() == 'true'
    MCP_SERVER_COMMAND = os.environ.get('MCP_SERVER_COMMAND')
    MCP_SERVER_ARGS = shlex.split(os.environ.get('MCP_SERVER_ARGS', ''))
    MCP_DATA_DIR = os.environ.get(
        'MCP_DATA_DIR',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../uploads'))
    )
    MCP_TABLE_SCHEMA_PATH = os.environ.get(
        'MCP_TABLE_SCHEMA_PATH',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../table_schema.json'))
    )
    MCP_TIMEOUT_SECONDS = float(os.environ.get('MCP_TIMEOUT_SECONDS', '30'))
    REPORT_FORCE_STRUCTURED_TABLE = os.environ.get(
        'REPORT_FORCE_STRUCTURED_TABLE', 'true'
    ).lower() == 'true'
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置"""
        errors: list[str] = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors
