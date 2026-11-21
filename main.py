"""BA 猜学生 —— 用是非题猜出你心里的碧蓝档案学生。

指令：/ba猜学生（开始）/ 放弃 / 重开 / 规则 / 统计
交互：QQ 官方原生按钮（是 / 不是 / 不确定 / 放弃）
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import ActionRow, Button, Plain
from astrbot.api.star import Context, Star, StarTools, register

PLUGIN_NAME = "astrbot_plugin_ba_20q"
MAX_CALLS_DEFAULT = 10
SESSION_TTL = 1800
IDLE_TIMEOUT = 180  # 3 分钟没操作视为放弃
CLICK_COOLDOWN = 1.5
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

# 开局切入角度：每局随机，避免每次都从学校问起
OPENINGS: tuple[str, ...] = (
    "学校",
    "社团",
    "发色或外观",
    "武器或战斗风格",
    "性格与说话方式",
    "剧情关系或所属组织",
    "是否联动作品",
    "年级或身高体型",
)

# ---------------------------------------------------------------- 题库
NAMES: tuple[str, ...] = (
    "爱露", "艾米", "晴奈", "日富美", "日奈", "星野", "伊织", "真纪",
    "妮露", "泉", "白子", "瞬", "堇", "鹤城", "泉奈", "爱丽丝",
    "绿", "切里诺", "柚子", "梓", "小春", "花凛", "明日奈", "夏",
    "千夏", "睦月", "若藻", "三森", "忧", "日向", "真里奈", "宫子",
    "美游", "月咏", "美咲", "亚津子", "野宫", "千世", "纱织", "和纱",
    "心奈", "歌原", "诺亚", "优香", "玛丽", "时雨", "芹娜", "美祢",
    "未花", "惠", "樱子", "时", "小雪", "佳代子", "果穗", "玲纱",
    "瑠海", "南", "咲", "花子", "芽瑠", "琴里", "一花", "霞",
    "御坂美琴", "食蜂操祈", "紫", "莲华", "桔梗", "小玉", "晴", "亚子",
    "海香", "好美", "绮罗罗", "桃", "康娜", "萌绘", "日和", "丽情",
    "千明", "圣娅", "濑名", "朱莉", "丽", "光", "望", "名草",
    "莲见", "绘里", "庚", "美代", "冬", "铃美", "昴", "贵音",
    "莉音", "柯伊", "木乃香", "丽奈", "妮可", "胡桃", "春香", "雪玲",
    "妃咲", "真琴", "皋月", "伊吕波", "心", "琴音", "安娜", "䌷",
    "茜", "明里", "纯子", "芹香", "椿", "桐乃", "红叶", "菲娜",
    "巴", "吹雪", "满", "响", "伊吹", "爱理", "青叶", "兰舞",
    "御伽", "纱绫", "真白", "初音未来", "和香", "千寻", "枫", "日鞠",
    "花江", "风香", "渚", "实梨", "尼娅", "律", "八云", "绘梨香",
    "艾莉娜", "绫音", "静子", "志美子", "佐天泪子", "拉娜", "阿罗娜", "普拉娜",
)

# 学校 → 成员（属性先验，帮助模型前几问就切对范围）
SCHOOLS: dict[str, tuple[str, ...]] = {
    '格黑娜': ('爱露', '晴奈', '日奈', '伊织', '泉', '千夏', '睦月', '惠', '佳代子', '霞', '亚子', '绮罗罗', '千明', '濑名', '朱莉', '春香', '真琴', '皋月', '伊吕波', '明里', '纯子', '伊吹', '风香', '绘梨香'),
    '千年': ('艾米', '真纪', '妮露', '堇', '爱丽丝', '绿', '柚子', '花凛', '明日奈', '歌原', '诺亚', '优香', '时', '小雪', '琴里', '小玉', '晴', '桃', '丽', '莉音', '柯伊', '茜', '响', '千寻', '日鞠'),
    '三一': ('日富美', '鹤城', '梓', '小春', '夏', '忧', '日向', '和纱', '玛丽', '芹娜', '美祢', '未花', '樱子', '玲纱', '花子', '一花', '好美', '圣娅', '莲见', '铃美', '爱理', '兰舞', '真白', '花江', '渚', '志美子'),
    '阿拜多斯': ('星野', '白子', '野宫', '芹香', '绫音'),
    '山海经': ('瞬', '心奈', '瑠海', '南', '丽情', '雪玲', '妃咲', '纱绫'),
    '百鬼夜行': ('泉奈', '若藻', '三森', '月咏', '千世', '果穗', '紫', '莲华', '桔梗', '海香', '名草', '椿', '菲娜', '满', '枫', '尼娅', '静子'),
    '红冬': ('切里诺', '真里奈', '时雨', '芽瑠', '贵音', '安娜', '红叶', '巴', '和香', '实梨', '八云', '艾莉娜', '拉娜'),
    'SRT': ('宫子', '美游', '咲', '萌绘', '妮可', '胡桃', '御伽'),
    '阿里乌斯': ('美咲', '亚津子', '纱织', '日和', '昴'),
    '常盘台': ('御坂美琴', '食蜂操祈'),
    '瓦尔基里': ('康娜', '木乃香', '桐乃', '吹雪'),
    '高地': ('光', '望', '青叶'),
    '狂猎': ('绘里', '庚', '美代', '冬', '丽奈', '䌷', '律'),
    '奥德赛': ('心', '琴音'),
    '联动/其他': ('初音未来',),
    '佐贺川': ('佐天泪子',),
    '其他/未分类': ('阿罗娜', '普拉娜'),
}

ALIASES: dict[str, tuple[str, ...]] = {
    '爱露': ('アル', 'Aru', '阿露'),
    '艾米': ('エイミ', 'Eimi', '艾美'),
    '晴奈': ('ハルナ', 'Haruna'),
    '日富美': ('ヒフミ', 'Hifumi'),
    '日奈': ('ヒナ', 'Hina', '委员长'),
    '星野': ('ホシノ', 'Hoshino', '大叔'),
    '伊织': ('イオリ', 'Iori'),
    '真纪': ('マキ', 'Maki'),
    '妮露': ('ネル', 'Neru', '宁瑠'),
    '泉': ('イズミ', 'Izumi'),
    '白子': ('シロコ', 'Shiroko'),
    '瞬': ('シュン', 'Shun', '舜'),
    '堇': ('スミレ', 'Sumire'),
    '鹤城': ('ツルギ', 'Tsurugi'),
    '泉奈': ('イズナ', 'Izuna'),
    '爱丽丝': ('アリス', 'Aris', '阿丽丝'),
    '绿': ('ミドリ', 'Midori'),
    '切里诺': ('チェリノ', 'Cherino'),
    '柚子': ('ユズ', 'Yuzu'),
    '梓': ('アズサ', 'Azusa'),
    '小春': ('コハル', 'Koharu'),
    '花凛': ('カリン', 'Karin', '卡琳'),
    '明日奈': ('アスナ', 'Asuna'),
    '夏': ('ナツ', 'Natsu'),
    '千夏': ('チナツ', 'Chinatsu'),
    '睦月': ('ムツキ', 'Mutsuki'),
    '若藻': ('ワカモ', 'Wakamo'),
    '三森': ('ミモリ', 'Mimori'),
    '忧': ('ウイ', 'Ui'),
    '日向': ('ヒナタ', 'Hinata'),
    '真里奈': ('マリナ', 'Marina', '玛丽娜'),
    '宫子': ('ミヤコ', 'Miyako'),
    '美游': ('ミユ', 'Miyu'),
    '月咏': ('ツクヨ', 'Tsukuyo'),
    '美咲': ('ミサキ', 'Misaki'),
    '亚津子': ('アツコ', 'Atsuko'),
    '野宫': ('ノノミ', 'Nonomi'),
    '千世': ('チセ', 'Chise'),
    '纱织': ('サオリ', 'Saori'),
    '和纱': ('カズサ', 'Kazusa'),
    '心奈': ('ココナ', 'Kokona', '可可娜'),
    '歌原': ('ウタハ', 'Utaha'),
    '诺亚': ('ノア', 'Noa'),
    '优香': ('ユウカ', 'Yuuka'),
    '玛丽': ('マリー', 'Mari'),
    '时雨': ('シグレ', 'Shigure'),
    '芹娜': ('セリナ', 'Serina', '塞莉娜'),
    '美祢': ('ミネ', 'Mine', '峰'),
    '未花': ('ミカ', 'Mika'),
    '惠': ('メグ', 'Megu'),
    '樱子': ('サクラコ', 'Sakurako'),
    '时': ('トキ', 'Toki'),
    '小雪': ('コユキ', 'Koyuki'),
    '佳代子': ('カヨコ', 'Kayoko'),
    '果穗': ('カホ', 'Kaho'),
    '玲纱': ('レイサ', 'Reisa'),
    '瑠海': ('ルミ', 'Rumi'),
    '南': ('ミナ', 'Mina'),
    '咲': ('サキ', 'Saki'),
    '花子': ('ハナコ', 'Hanako'),
    '芽瑠': ('メル', 'Meru'),
    '琴里': ('コトリ', 'Kotori'),
    '一花': ('イチカ', 'Ichika'),
    '霞': ('カスミ', 'Kasumi'),
    '御坂美琴': ('MisakaMikoto', '美琴', 'Misaka'),
    '食蜂操祈': ('ShokuhouMisaki', '食蜂', 'Shokuhou'),
    '紫': ('ユカリ', 'Yukari'),
    '莲华': ('レンゲ', 'Renge'),
    '桔梗': ('キキョウ', 'Kikyou'),
    '小玉': ('コタマ', 'Kotama', '小弹'),
    '晴': ('ハレ', 'Hare', '哈雷'),
    '亚子': ('アコ', 'Ako'),
    '海香': ('ウミカ', 'Umika'),
    '好美': ('ヨシミ', 'Yoshimi'),
    '绮罗罗': ('キララ', 'Kirara'),
    '桃': ('モモイ', 'Momoi'),
    '康娜': ('カンナ', 'Kanna'),
    '萌绘': ('モエ', 'Moe'),
    '日和': ('ヒヨリ', 'Hiyori'),
    '丽情': ('レイジョ', 'Reijo'),
    '千明': ('チアキ', 'Chiaki'),
    '圣娅': ('セイア', 'Seia'),
    '濑名': ('セナ', 'Sena'),
    '朱莉': ('ジュリ', 'Juri'),
    '丽': ('レイ', 'Rei'),
    '光': ('ヒカリ', 'Hikari'),
    '望': ('ノゾミ', 'Nozomi'),
    '名草': ('ナグサ', 'Nagusa'),
    '莲见': ('ハスミ', 'Hasumi'),
    '绘里': ('エリ', 'Eri'),
    '庚': ('カノエ', 'Kanoe'),
    '美代': ('ミヨ', 'Miyo'),
    '冬': ('フユ', 'Fuyu'),
    '铃美': ('スズミ', 'Suzumi'),
    '昴': ('スバル', 'Subaru'),
    '贵音': ('タカネ', 'Takane'),
    '莉音': ('リオ', 'Rio'),
    '柯伊': ('ケイ', 'Kei', '凯伊'),
    '木乃香': ('コノカ', 'Konoka'),
    '丽奈': ('レナ', 'Rena'),
    '妮可': ('ニコ', 'Niko'),
    '胡桃': ('クルミ', 'Kurumi'),
    '春香': ('ハルカ', 'Haruka'),
    '妃咲': ('キサキ', 'Kisaki'),
    '真琴': ('マコト', 'Makoto'),
    '皋月': ('サツキ', 'Satsuki'),
    '伊吕波': ('イロハ', 'Iroha'),
    '心': ('ココロ', 'Kokoro'),
    '琴音': ('コトネ', 'Kotone'),
    '安娜': ('アンナ', 'Anna'),
    '䌷': ('ツムギ', 'Tsumugi'),
    '茜': ('アカネ', 'Akane'),
    '明里': ('アカリ', 'Akari'),
    '纯子': ('ジュンコ', 'Junko'),
    '芹香': ('セリカ', 'Serika'),
    '椿': ('ツバキ', 'Tsubaki'),
    '桐乃': ('キリノ', 'Kirino'),
    '红叶': ('モミジ', 'Momiji'),
    '菲娜': ('フィーナ', 'Pina'),
    '巴': ('トモエ', 'Tomoe'),
    '吹雪': ('フブキ', 'Fubuki'),
    '满': ('ミチル', 'Michiru'),
    '响': ('ヒビキ', 'Hibiki'),
    '伊吹': ('イブキ', 'Ibuki'),
    '爱理': ('アイリ', 'Airi'),
    '青叶': ('アオバ', 'Aoba'),
    '兰舞': ('ラブ', 'Rabu'),
    '御伽': ('オトギ', 'Otogi'),
    '纱绫': ('サヤ', 'Saya'),
    '真白': ('マシロ', 'Mashiro'),
    '初音未来': ('初音ミク', 'HatsuneMiku', '初音', 'Miku'),
    '和香': ('ノドカ', 'Nodoka'),
    '千寻': ('チヒロ', 'Chihiro'),
    '枫': ('カエデ', 'Kaede'),
    '日鞠': ('ヒマリ', 'Himari', '阳鞠'),
    '花江': ('ハナエ', 'Hanae', '花惠'),
    '风香': ('フウカ', 'Fuuka'),
    '渚': ('ナギサ', 'Nagisa'),
    '实梨': ('ミノリ', 'Minori'),
    '尼娅': ('ニヤ', 'Niya'),
    '律': ('リツ', 'Ritsu'),
    '八云': ('ヤクモ', 'Yakumo'),
    '绘梨香': ('エリカ', 'Erika'),
    '艾莉娜': ('エリナ', 'Erina'),
    '绫音': ('アヤネ', 'Ayane'),
    '静子': ('シズコ', 'Shizuko'),
    '志美子': ('シミコ', 'Shimiko'),
    '佐天泪子': ('佐天涙子', 'SatenRuiko', '佐天', 'Saten'),
    '阿罗娜': ('Arona',),
    '普拉娜': ('Plana',),
}

ALIASES.setdefault("雪玲", ("Shunling", "雪玲"))
ALIASES.setdefault("拉娜", ("Lana", "ラナ"))

CLUBS: dict[str, tuple[str, ...]] = {
    '便利屋68': ('爱露', '佳代子', '睦月', '春香'),
    'SPTF': ('艾米', '日鞠', '柯伊'),
    '美食研究会': ('晴奈', '泉', '明里', '纯子'),
    '补习部': ('日富美', '梓', '花子', '小春'),
    '风纪委员会': ('日奈', '伊织', '千夏', '亚子'),
    '对策委员会': ('星野', '白子', '野宫', '芹香', '绫音'),
    '真理部': ('真纪', '晴', '小玉', '千寻'),
    'C&C': ('妮露', '茜', '明日奈', '花凛', '时'),
    '梅花园': ('瞬', '心奈', '雪玲'),
    '正义实现委员会': ('鹤城', '莲见', '真白', '一花'),
    '阴阳部': ('千世', '果穗', '尼娅'),
    '修行部': ('椿', '三森', '枫'),
    '研讨会': ('优香', '诺亚', '小雪', '莉音'),
    '工程部': ('琴里', '响', '歌原'),
    '放学后甜点部': ('爱理', '好美', '夏', '和纱'),
    '救护骑士团': ('花江', '芹娜', '美祢'),
    '忍术研究部': ('泉奈', '满', '月咏'),
    '游戏开发部': ('爱丽丝', '绿', '桃', '柚子'),
    '修女会': ('玛丽', '日向', '樱子'),
    '兔子小队': ('宫子', '咲', '美游', '萌绘'),
    '万魔殿': ('伊吕波', '伊吹', '真琴', '千明', '皋月'),
    '阿里乌斯小队': ('美咲', '日和', '亚津子', '纱织'),
    '茶会': ('未花', '渚', '圣娅'),
    '百花缭乱': ('紫', '莲华', '桔梗', '名草'),
}

PROMPT_SYSTEM = """你在主持《碧蓝档案》学生猜谜游戏（类似 Akinator）。老师心里想的是名单里某一位学生。你要靠提问把范围缩小到她。

提问规则：
1. 每次只问一个问题，必须能用「是 / 不是 / 不确定」回答。
2. 问题要能有效缩小范围，可以是学校、社团、发色、武器、性格、剧情、联动等任何角度。
3. 不要每次都从学校开始；开局角度要多样，别让玩家一眼看出套路。
4. 严禁直接问名字（如「她是不是叫白子」），严禁把候选人名字写进问题。
5. 不要重复已问过的问题，也不要重新猜已排除的名字。
6. 前 4 问不要急着猜；之后觉得有把握就猜。
7. 最多 {max_q} 次思考。

输出格式（只输出一种，不要解释）：
ASK: <属性问题，不超过 30 字>
或
GUESS: <学生名，必须严格来自名单>
"""


@register(PLUGIN_NAME, "chen", "碧蓝档案猜学生：用是非题猜出角色", "1.1.0")
class BA20QPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_file = self.data_dir / "sessions.json"
        self.stats_file = self.data_dir / "stats.json"
        self.sessions: dict[str, dict] = self._load_json(self.sessions_file)
        self.stats: dict[str, dict] = self._load_json(self.stats_file)
        self._cleaner_task: asyncio.Task | None = None
        logger.info(f"[BA20Q] 已加载，角色库 {len(NAMES)} 位")

    async def initialize(self):
        if self._cleaner_task is None:
            self._cleaner_task = asyncio.create_task(self._cleaner_loop())
            logger.info("[BA20Q] 过期会话清理任务已启动")

    async def terminate(self):
        if self._cleaner_task is not None:
            self._cleaner_task.cancel()
            self._cleaner_task = None

    # ---------------- 存储 ----------------
    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.warning(f"[BA20Q] 读取 {path.name} 失败: {exc}")
        return {}

    def _save_sessions(self) -> None:
        try:
            self.sessions_file.write_text(
                json.dumps(self.sessions, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"[BA20Q] 保存会话失败: {exc}")

    def _save_stats(self) -> None:
        try:
            self.stats_file.write_text(
                json.dumps(self.stats, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"[BA20Q] 保存统计失败: {exc}")

    def _group_key(self, event: AstrMessageEvent) -> str:
        gid = str(event.get_group_id() or "")
        if gid:
            return gid
        return "private:" + str(event.get_sender_id() or "")

    def _close_idle(self) -> int:
        """超时未操作的对局按放弃处理（计入负场）。"""
        now = time.time()
        closed = 0
        for key in list(self.sessions):
            sess = self.sessions.get(key) or {}
            idle = now - float(sess.get("ts", 0) or 0)
            if idle > IDLE_TIMEOUT:
                self.sessions.pop(key, None)
                closed += 1
                logger.info(
                    f"[BA20Q] 对局超时自动结束（{int(idle)}s）：{sess.get('owner_name', '')}"
                )
        if closed:
            self._save_sessions()
        return closed

    def _clean_expired(self) -> int:
        now = time.time()
        removed = 0
        for key in list(self.sessions):
            sess = self.sessions.get(key) or {}
            if now - float(sess.get("ts", 0) or 0) > SESSION_TTL:
                self.sessions.pop(key, None)
                removed += 1
        if removed:
            self._save_sessions()
        return removed

    async def _cleaner_loop(self):
        try:
            while True:
                await asyncio.sleep(60)
                try:
                    n = self._close_idle()
                    if n:
                        logger.info(f"[BA20Q] 超时结束对局 {n} 个")
                    self._clean_expired()
                except Exception as exc:
                    logger.warning(f"[BA20Q] 定期清理失败: {exc}")
        except asyncio.CancelledError:
            pass

    # ---------------- 模型 ----------------
    async def _direct_chat(self, system_prompt: str, user_prompt: str) -> str:
        import aiohttp

        base = str(self.config.get("api_base", DEFAULT_API_BASE) or DEFAULT_API_BASE)
        model = str(self.config.get("model", DEFAULT_MODEL) or DEFAULT_MODEL)
        key = str(self.config.get("api_key", "") or "").strip()
        url = base.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "max_tokens": 200,
            "temperature": 0.7,
        }
        timeout = float(self.config.get("timeout", 45) or 45)
        async with aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.post(
                url, json=payload, headers={"Authorization": f"Bearer {key}"}
            ) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}: {body[:120]}")
                data = json.loads(body)
                msg = (data.get("choices") or [{}])[0].get("message") or {}
                return str(msg.get("content") or "").strip()

    @staticmethod
    def _alias_hint() -> str:
        parts = []
        for name, al in ALIASES.items():
            if al:
                parts.append(f"{'/'.join(al)}={name}")
        return "；".join(parts)

    @staticmethod
    def _club_hint() -> str:
        parts = []
        for club, members in CLUBS.items():
            parts.append(f"{club}：{'、'.join(members)}")
        return "；".join(parts)

    @staticmethod
    def _school_hint() -> str:
        parts = []
        for school, members in SCHOOLS.items():
            parts.append(f"{school}：{'、'.join(members)}")
        return "\n".join(parts)

    async def _ask_ai(self, sess: dict) -> tuple[str, str]:
        provider = None
        if not str(self.config.get("api_key", "") or "").strip():
            provider = self.context.get_using_provider()
            if provider is None:
                return "error", "当前没有可用的对话模型"

        max_calls = int(self.config.get("max_calls", MAX_CALLS_DEFAULT) or MAX_CALLS_DEFAULT)
        calls = int(sess.get("calls", 0) or 0) + 1
        sess["calls"] = calls
        history = sess.get("history") or []
        excluded = sess.get("excluded") or []
        hist_text = "\n".join(f"{i + 1}. {h['q']} → {h['a']}" for i, h in enumerate(history)) or "（还没有）"
        prompt = (
            f"学生名单：{'、'.join(NAMES)}\n\n"
            f"别名对照（日文名/罗马音/常用叫法 → 名单里的名字）：\n{self._alias_hint()}\n\n"
            f"社团参考：\n{self._club_hint()}\n\n"
            f"已问过的问题与回答：\n{hist_text}\n\n"
            f"已经猜错、必须排除的名字：{'、'.join(excluded) if excluded else '（无）'}\n\n"
            + (
                f"开局要求：第一个问题请从「{sess.get('opening', '学校')}」切入，别每次都问学校。\n\n"
                if not history
                else ""
            )
            + f"这是第 {len(history) + 1} 个问题，本局最多 {max_calls} 次思考（当前第 {calls} 次）。"
            + ("这已经是最后一次机会，必须直接给出 GUESS。" if calls >= max_calls else "")
            + "\n请输出 ASK 或 GUESS。"
        )

        last_error = "未知错误"
        for attempt in range(2):
            try:
                sys_prompt = PROMPT_SYSTEM.format(max_q=max_calls)
                if provider is not None:
                    resp = await asyncio.wait_for(
                        provider.text_chat(
                            prompt=prompt, system_prompt=sys_prompt, contexts=[]
                        ),
                        timeout=float(self.config.get("timeout", 45) or 45),
                    )
                    text = (getattr(resp, "completion_text", "") or "").strip()
                else:
                    text = await self._direct_chat(sys_prompt, prompt)
                kind, value = self._parse_reply(text)
                if kind:
                    return kind, value
                last_error = "模型没有给出有效问题"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    f"[BA20Q] 调用失败（第 {attempt + 1} 次）: {last_error}"
                )
                await asyncio.sleep(0.8)
        return "error", last_error

    @staticmethod
    def _parse_reply(text: str) -> tuple[str, str]:
        guess = re.search(r"GUESS[:：]\s*(.+)", text)
        ask = re.search(r"ASK[:：]\s*(.+)", text)
        if guess:
            name = guess.group(1).strip().splitlines()[0].strip(" 　\"'「」")
            if name in NAMES:
                return "guess", name
            if ask:
                return "ask", ask.group(1).strip().splitlines()[0][:60]
            return "", ""
        if ask:
            return "ask", ask.group(1).strip().splitlines()[0][:60]
        line = text.splitlines()[0].strip() if text else ""
        if line:
            return "ask", line[:60]
        return "", ""

    # ---------------- 渲染 ----------------
    @staticmethod
    def _buttons(sess_id: str, guessing: bool) -> list:
        if guessing:
            return [
                ActionRow(
                    buttons=[
                        Button(
                            id=f"ba20q-right-{sess_id}",
                            label="对！就是她",
                            action=Button.CallbackAction(data=f"ba20q:{sess_id}:right"),
                            style=Button.Style.PRIMARY,
                        ),
                        Button(
                            id=f"ba20q-wrong-{sess_id}",
                            label="不对",
                            action=Button.CallbackAction(data=f"ba20q:{sess_id}:wrong"),
                            style=Button.Style.DANGER,
                        ),
                    ]
                )
            ]
        return [
            ActionRow(
                buttons=[
                    Button(
                        id=f"ba20q-yes-{sess_id}",
                        label="是",
                        action=Button.CallbackAction(data=f"ba20q:{sess_id}:yes"),
                        style=Button.Style.PRIMARY,
                    ),
                    Button(
                        id=f"ba20q-no-{sess_id}",
                        label="不是",
                        action=Button.CallbackAction(data=f"ba20q:{sess_id}:no"),
                        style=Button.Style.DANGER,
                    ),
                    Button(
                        id=f"ba20q-idk-{sess_id}",
                        label="不确定",
                        action=Button.CallbackAction(data=f"ba20q:{sess_id}:unknown"),
                        style=Button.Style.DEFAULT,
                    ),
                    Button(
                        id=f"ba20q-giveup-{sess_id}",
                        label="放弃",
                        action=Button.CallbackAction(data=f"ba20q:{sess_id}:giveup"),
                        style=Button.Style.DEFAULT,
                    ),
                ]
            )
        ]

    @staticmethod
    def _end_buttons() -> list:
        return [
            ActionRow(
                buttons=[
                    Button(
                        id="ba20q-again",
                        label="🔄 再来一局",
                        action=Button.CallbackAction(data="ba20q:again:start"),
                        style=Button.Style.PRIMARY,
                    ),
                    Button(
                        id="ba20q-stats",
                        label="📊 本群统计",
                        action=Button.CallbackAction(data="ba20q:stats:show"),
                        style=Button.Style.DEFAULT,
                    ),
                ]
            )
        ]

    async def _begin_game(self, event: AstrMessageEvent) -> tuple[str, list | None]:
        """开一局：成功返回 ("", 组件列表)，失败返回 (错误文案, None)。"""
        gid = self._group_key(event)
        uid = str(event.get_sender_id() or "")
        sess = self.sessions.get(gid)
        if sess:
            who = sess.get("owner_name") or "有人"
            return (
                f"本群已有一局在进行（{who}），等 ta 答完再来～"
                if sess.get("owner") != uid
                else "你已经在玩啦，直接回答上面的问题就好～",
                None,
            )

        max_calls = int(self.config.get("max_calls", MAX_CALLS_DEFAULT) or MAX_CALLS_DEFAULT)
        sess_id = f"{random.randint(1000, 9999)}{int(time.time()) % 1000:03d}"
        sess = {
            "id": sess_id,
            "owner": uid,
            "owner_name": (event.get_sender_name() or "").strip() or "某位老师",
            "question": "",
            "history": [],
            "excluded": [],
            "guess": "",
            "calls": 0,
            "max_calls": max_calls,
            "opening": random.choice(OPENINGS),
            "busy": False,
            "ts": time.time(),
        }
        kind, text = await self._ask_ai(sess)
        if kind == "error":
            return f"开局失败：{text}", None
        if kind == "guess":
            sess["guess"] = text
            sess["state"] = "guessing"
            self.sessions[gid] = sess
            self._save_sessions()
            return "", (
                [Plain(f"🤔 阿罗娜好像知道了……\n\n你心里想的是不是「{text}」？")]
                + self._buttons(sess_id, guessing=True)
            )
        sess["question"] = text
        sess["state"] = "asking"
        self.sessions[gid] = sess
        self._save_sessions()
        return "", (
            [Plain(self._question_text(sess))]
            + self._buttons(sess_id, guessing=False)
        )

    def _question_text(self, sess: dict) -> str:
        max_calls = int(sess.get("max_calls", MAX_CALLS_DEFAULT) or MAX_CALLS_DEFAULT)
        history = sess.get("history") or []
        q_no = len(history) + 1
        lines = [
            f"🔮 BA 猜学生 · 第 {q_no}/{max_calls} 问",
            "",
            f"❓ {sess.get('question', '')}",
        ]
        if history:
            shown = history[-3:]
            lines.append("")
            lines.append("已答：" + " → ".join(h["a"] for h in shown))
            if len(history) > 3:
                lines[-1] += f"（共 {len(history)} 问）"
        return "\n".join(lines)

    # ---------------- 统计 ----------------
    def _stat_game(self, gid: str, win: bool, questions: int = 0):
        rec = self.stats.setdefault(
            gid,
            {"games": 0, "wins": 0, "total_q": 0, "best_q": 0, "last_ts": 0},
        )
        rec["games"] = int(rec.get("games", 0)) + 1
        rec["last_ts"] = int(time.time())
        if win:
            rec["wins"] = int(rec.get("wins", 0)) + 1
            rec["total_q"] = int(rec.get("total_q", 0)) + max(0, questions)
            best = int(rec.get("best_q", 0) or 0)
            if questions > 0 and (best == 0 or questions < best):
                rec["best_q"] = questions
        self._save_stats()

    def _stats_text(self, gid: str) -> str:
        rec = self.stats.get(gid) or {}
        games = int(rec.get("games", 0))
        wins = int(rec.get("wins", 0))
        total_q = int(rec.get("total_q", 0))
        best_q = int(rec.get("best_q", 0) or 0)
        last_ts = int(rec.get("last_ts", 0) or 0)
        if not games:
            return "📊 本群还没有玩过，发 /ba猜学生 开始第一局吧～"
        rate = wins / games * 100
        avg = (total_q / wins) if wins else 0
        lines = [
            "📊 本群 BA 猜学生统计（累计）",
            "",
            f"总局数：{games}",
            f"猜中：{wins} 局",
            f"猜中率：{rate:.0f}%",
            f"平均用问：{avg:.1f} 问（只统计猜中的）",
        ]
        if best_q:
            lines.append(f"最佳纪录：{best_q} 问猜中")
        if last_ts:
            lines.append(
                "最近一局：" + time.strftime("%Y-%m-%d %H:%M", time.localtime(last_ts))
            )
        lines.append("")
        lines.append("记录永久累计，不会因为清理对局而丢失。")
        return "\n".join(lines)

    # ---------------- 指令 ----------------
    @filter.regex(r"(?i)^[\s/]*ba猜学生(?:\s+(放弃|结束|重开|规则|统计))?$")
    async def ba_guess_student(self, event: AstrMessageEvent):
        event.stop_event()
        raw = (event.message_str or "").strip()
        m = re.search(r"ba猜学生\s+(放弃|结束|重开|规则|统计)", raw, re.IGNORECASE)
        arg = m.group(1) if m else ""

        gid = self._group_key(event)
        self._clean_expired()
        sess = self.sessions.get(gid)
        uid = str(event.get_sender_id() or "")

        if sess and time.time() - float(sess.get("ts", 0) or 0) > IDLE_TIMEOUT:
            self.sessions.pop(gid, None)
            self._save_sessions()
            sess = None

        if arg == "规则":
            yield event.plain_result(
                "📖 BA 猜学生\n\n"
                "用「是 / 不是 / 不确定」回答阿罗娜的问题，"
                "她最多思考 10 次就会猜出你心里的碧蓝档案学生。\n\n"
                "指令：\n"
                "  /ba猜学生       开始一局\n"
                "  /ba猜学生 放弃   结束当前这局\n"
                "  /ba猜学生 重开   重新开一局\n"
                "  /ba猜学生 统计   查看本群战绩\n\n"
                "每群同时只能有 1 局；超过 3 分钟没操作会自动算放弃。"
            )
            return

        if arg == "统计":
            yield event.plain_result(self._stats_text(gid))
            return

        if arg in ("放弃", "结束"):
            if not sess:
                yield event.plain_result("现在没有进行中的对局哦～")
                return
            if sess.get("owner") != uid and not event.is_admin():
                who = sess.get("owner_name") or "别人"
                yield event.plain_result(f"现在是 {who} 的对局，要结束请让 ta 自己发～")
                return
            guess = sess.get("guess") or ""
            self.sessions.pop(gid, None)
            self._save_sessions()
            extra = f"\n阿罗娜本来想猜：{guess}" if guess else ""
            yield event.chain_result(
                [Plain("已结束本局（不计入统计）。" + extra)] + self._end_buttons()
            )
            return

        if sess and arg != "重开":
            who = sess.get("owner_name") or "有人"
            yield event.plain_result(
                f"本群已有一局在进行（{who}），等 ta 答完，"
                "或让 ta 发 /ba猜学生 放弃 再来～"
            )
            return

        if arg == "重开":
            if sess and sess.get("owner") != uid and not event.is_admin():
                who = sess.get("owner_name") or "别人"
                yield event.plain_result(f"现在是 {who} 的对局，要重开请让 ta 自己发～")
                return
            self.sessions.pop(gid, None)

        err, comps = await self._begin_game(event)
        if comps is None:
            yield event.plain_result(err)
            return
        yield event.chain_result(comps)

    # ---------------- 按钮 ----------------
    @filter.button_action()
    async def on_button(self, event: AstrMessageEvent):
        data = ""
        for comp in event.get_messages():
            if type(comp).__name__ == "ButtonInteraction":
                data = str(getattr(comp, "data", "") or "")
                break
        if not data.startswith("ba20q:"):
            return
        event.stop_event()
        parts = data.split(":")
        if len(parts) >= 2 and parts[1] == "stats":
            yield event.chain_result(
                [Plain(self._stats_text(self._group_key(event)))]
                + self._end_buttons()
            )
            return
        if len(parts) >= 2 and parts[1] == "again":
            err, comps = await self._begin_game(event)
            if comps is None:
                yield event.chain_result([Plain(err)] + self._end_buttons())
            else:
                yield event.chain_result(comps)
            return
        if len(parts) < 3:
            return
        sess_id, action = parts[1], parts[2]
        gid = self._group_key(event)
        sess = self.sessions.get(gid)
        uid = str(event.get_sender_id() or "")
        if not sess or sess.get("id") != sess_id:
            yield event.plain_result("这局已经结束啦，发 /ba猜学生 再开一局吧～")
            return
        if time.time() - float(sess.get("ts", 0) or 0) > IDLE_TIMEOUT:
            self.sessions.pop(gid, None)
            self._save_sessions()
            yield event.chain_result(
                [Plain("⏳ 超过 3 分钟没操作，这局先关掉啦（不计入统计）～ 想玩发 /ba猜学生。")]
                + self._end_buttons()
            )
            return
        if sess.get("owner") != uid and not event.is_admin():
            who = sess.get("owner_name") or "别人"
            yield event.plain_result(f"这是 {who} 的对局哦，让 ta 自己回答～")
            return
        # 防连点
        now = time.time()
        if sess.get("busy") and now - float(sess.get("ts", 0) or 0) < CLICK_COOLDOWN:
            yield event.plain_result("别点太快啦，阿罗娜还在想…")
            return
        sess["busy"] = True
        sess["ts"] = now

        try:
            async for result in self._handle_action(event, sess, gid, sess_id, action):
                yield result
        finally:
            sess["busy"] = False
            sess["ts"] = time.time()
            if self.sessions.get(gid) is sess:
                self._save_sessions()

    async def _handle_action(self, event, sess, gid, sess_id, action):
        max_calls = int(sess.get("max_calls", MAX_CALLS_DEFAULT) or MAX_CALLS_DEFAULT)

        if action == "giveup":
            self.sessions.pop(gid, None)
            self._save_sessions()
            yield event.chain_result(
                [Plain("好，这局先到这里（不计入统计）。发 /ba猜学生 可以再玩一次～")]
                + self._end_buttons()
            )
            return

        if action == "right":
            q_used = len(sess.get("history") or [])
            self._stat_game(gid, win=True, questions=q_used)
            name = sess.get("guess", "")
            self.sessions.pop(gid, None)
            self._save_sessions()
            yield event.chain_result(
                [
                    Plain(
                        f"🎉 猜中啦！{name}\n阿罗娜用了 {q_used} 个问题就看穿你了～"
                    )
                ]
                + self._end_buttons()
            )
            return

        if action == "wrong":
            guess = sess.get("guess", "")
            if guess:
                sess.setdefault("excluded", []).append(guess)
            sess["guess"] = ""
            sess["history"].append({"q": f"是「{guess}」吗？", "a": "不是"})

        elif action in ("yes", "no", "unknown"):
            answer_map = {"yes": "是", "no": "不是", "unknown": "不确定"}
            sess["history"].append(
                {"q": sess.get("question", ""), "a": answer_map[action]}
            )
        else:
            return

        calls = int(sess.get("calls", 0) or 0)
        if calls >= max_calls and action == "wrong":
            # 最后一次机会也猜错了，判定失败
            self._stat_game(gid, win=False)
            self.sessions.pop(gid, None)
            self._save_sessions()
            yield event.chain_result(
                [Plain("😵 机会用完了，这局没猜中。发 /ba猜学生 再来一局吧～")]
                + self._end_buttons()
            )
            return

        kind, text = await self._ask_ai(sess)
        if kind == "error":
            yield event.plain_result(f"阿罗娜卡壳了：{text}")
            return
        if kind == "guess":
            sess["guess"] = text
            sess["state"] = "guessing"
            self.sessions[gid] = sess
            self._save_sessions()
            yield event.chain_result(
                [Plain(f"🤔 阿罗娜猜你想的是「{text}」，对吗？")]
                + self._buttons(sess_id, guessing=True)
            )
            return
        sess["question"] = text
        sess["state"] = "asking"
        self.sessions[gid] = sess
        self._save_sessions()
        yield event.chain_result(
            [Plain(self._question_text(sess))] + self._buttons(sess_id, guessing=False)
        )
