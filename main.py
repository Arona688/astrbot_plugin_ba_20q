"""BA 猜学生 —— 用是非题猜出你心里的碧蓝档案学生。

指令：/ba猜学生（开始）/ 放弃 / 重开 / 规则 / 统计
交互：QQ 官方原生按钮（是 / 不是 / 放弃）
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
from astrbot.api.message_components import ActionRow, Button, Image, Plain
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.message.message_event_result import MessageChain

PLUGIN_NAME = "astrbot_plugin_ba_20q"
ROSTER_PATH = Path(__file__).parent / "roster.png"
MAX_QUESTIONS_DEFAULT = 12
MAX_CALLS_DEFAULT = 13
MIN_QUESTIONS = 8
COSTUME_MAX_QUESTIONS = 16
SESSION_TTL = 1800
IDLE_TIMEOUT = 120  # 2 分钟没操作视为放弃
CLICK_COOLDOWN = 1.5
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

# 开局切入角度：每局随机，避免每次都从学校问起
OPENINGS: tuple[str, ...] = (
    "学校",
    "社团",
    "年级或年龄",
    "武器种类",
    "战术定位或站位",
    "性格与说话方式",
    "爱好",
    "剧情关系或所属组织",
    "是否联动作品",
)

# ---------------------------------------------------------------- 题库
NAMES: tuple[str, ...] = (
    '阿露', '艾米', '晴奈', '日富美', '日奈', '星野', '伊织', '真纪',
    '妮露', '泉', '白子', '瞬', '堇', '鹤城', '泉奈', '爱丽丝',
    '绿', '切里诺', '柚子', '梓', '小春', '卡琳', '明日奈', '夏',
    '千夏', '睦月', '若藻', '三森', '忧', '日向', '真里奈', '宫子',
    '美游', '月咏', '美咲', '亚津子', '野宫', '千世', '纱织', '和纱',
    '心奈', '歌原', '诺亚', '优香', '玛丽', '时雨', '芹娜', '美祢',
    '未花', '惠', '樱子', '时', '小雪', '佳代子', '果穗', '玲纱',
    '瑠海', '南', '咲', '花子', '芽瑠', '琴里', '一花', '霞',
    '御坂美琴', '食蜂操祈', '紫', '莲华', '桔梗', '小玉', '晴', '亚子',
    '海香', '好美', '绮罗罗', '桃', '康娜', '萌绘', '日和', '丽情',
    '千明', '圣娅', '濑名', '朱莉', '光', '望', '名草', '莲见',
    '庚', '美代', '冬', '铃美', '昴', '贵音', '莉音', '柯伊',
    '蕾娜', '妮可', '胡桃', '春香', '雪玲', '妃咲', '真琴', '皋月',
    '伊吕波', '心', '琴音', '安娜', '茜', '明里', '纯子', '芹香',
    '椿', '桐乃', '红叶', '菲娜', '巴', '吹雪', '满', '响',
    '伊吹', '爱理', '青叶', '兰舞', '御伽', '纱绫', '真白', '初音未来',
    '和香', '千寻', '枫', '日鞠', '花江', '风香', '渚', '实梨',
    '尼娅', '律', '八云', '绘梨香', '绫音', '静子', '志美子', '佐天泪子',
    '阿罗娜', '普拉娜',
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
    '阿露': ('アル', 'Aru', '阿露'),
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
    '卡琳': ('カリン', 'Karin', '卡琳'),
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
    '光': ('ヒカリ', 'Hikari'),
    '望': ('ノゾミ', 'Nozomi'),
    '名草': ('ナグサ', 'Nagusa'),
    '莲见': ('ハスミ', 'Hasumi'),
    '庚': ('カノエ', 'Kanoe'),
    '美代': ('ミヨ', 'Miyo'),
    '冬': ('フユ', 'Fuyu'),
    '铃美': ('スズミ', 'Suzumi'),
    '昴': ('スバル', 'Subaru'),
    '贵音': ('タカネ', 'Takane'),
    '莉音': ('リオ', 'Rio'),
    '柯伊': ('ケイ', 'Kei', '凯伊'),
    '蕾娜': ('レナ', 'Rena'),
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
    '绫音': ('アヤネ', 'Ayane'),
    '静子': ('シズコ', 'Shizuko'),
    '志美子': ('シミコ', 'Shimiko'),
    '佐天泪子': ('佐天涙子', 'SatenRuiko', '佐天', 'Saten'),
    '阿罗娜': ('Arona',),
    '普拉娜': ('Plana',),
}

ALIASES.setdefault("雪玲", ("Shunling", "雪玲"))
ALIASES.setdefault("蕾娜", ("レナ", "Rena"))
ALIASES['阿露'] = tuple(ALIASES.get('阿露', ())) + ('爱露',)
ALIASES['蕾娜'] = tuple(ALIASES.get('蕾娜', ())) + ('丽奈',)
ALIASES['卡琳'] = tuple(ALIASES.get('卡琳', ())) + ('花凛',)

ATTRIBUTES: tuple[str, ...] = (
    '阿露｜格黑娜｜便利屋68｜2年级｜狙击枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜学习经营',
    '艾米｜千年｜超自然现象研究部｜1年级｜霰弹枪｜爆发｜坦克｜前排｜3星｜原版｜—｜—｜发呆、听音乐',
    '晴奈｜格黑娜｜美食研究会｜3年级｜狙击枪｜神秘｜输出｜后排｜3星｜原版｜—｜—｜美食探店、制作美食清单',
    '日富美｜三一｜补习部｜2年级｜突击步枪｜贯穿｜辅助｜中排｜3星｜原版｜—｜—｜收集佩洛洛周边玩具、购物、做倾听者',
    '日奈｜格黑娜｜风纪委员会｜3年级｜重机枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜睡眠、休息',
    '星野｜阿拜多斯｜对策委员会｜3年级｜霰弹枪｜贯穿｜坦克｜前排｜3星｜原版｜—｜—｜白天睡觉、偷懒',
    '伊织｜格黑娜｜风纪委员会｜2年级｜狙击枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜巡逻、训斥人',
    '真纪｜千年｜真理部｜1年级｜重机枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜涂鸦、打游戏',
    '妮露｜千年｜C&C｜3年级｜冲锋枪｜贯穿｜输出｜前排｜3星｜原版｜—｜—｜胜利',
    '泉｜格黑娜｜美食研究会｜2年级｜重机枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜制作黑暗料理、享用黑暗料理',
    '白子｜阿拜多斯｜对策委员会｜2年级｜突击步枪｜爆发｜输出｜中排｜3星｜原版｜—｜—｜慢跑、体能训练、骑自行车',
    '瞬｜山海经｜梅花园｜3年级｜狙击枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜和孩子们玩耍',
    '堇｜千年｜健身部｜2年级｜霰弹枪｜贯穿｜输出｜前排｜3星｜原版｜—｜—｜园艺、运动',
    '鹤城｜三一｜正义实现部｜3年级｜霰弹枪｜贯穿｜输出｜前排｜3星｜原版｜—｜—｜看电影、读言情小说',
    '泉奈｜百鬼夜行｜忍术研究部｜1年级｜冲锋枪｜神秘｜输出｜前排｜3星｜原版｜—｜—｜学习忍法卷轴、保护主公',
    '爱丽丝｜千年｜游戏开发部｜1年级｜轨道炮｜神秘｜输出｜后排｜3星｜原版｜—｜—｜游戏（RPG）',
    '绿｜千年｜游戏开发部｜1年级｜狙击枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜绘画',
    '切里诺｜红冬｜红冬秘书处｜3年级｜手枪｜贯穿｜输出｜中排｜3星｜原版｜—｜—｜铲除、打雪仗',
    '柚子｜千年｜游戏开发部｜1年级｜榴弹发射器｜贯穿｜输出｜中排｜3星｜原版｜—｜—｜制作游戏',
    '梓｜三一｜补习部｜2年级｜突击步枪｜爆发｜输出｜中排｜3星｜原版｜—｜—｜无',
    '小春｜三一｜补习部｜1年级｜狙击枪｜爆发｜治疗｜后排｜3星｜原版｜—｜—｜空想、妄想、收集色色的杂志',
    '卡琳｜千年｜C&C｜2年级｜狙击枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜清洁',
    '明日奈｜千年｜C&C｜3年级｜突击步枪｜神秘｜输出｜中排｜1星｜原版｜—｜—｜突袭',
    '夏｜三一｜放学后甜点部｜1年级｜冲锋枪｜神秘｜坦克｜前排｜3星｜原版｜—｜—｜浪漫的东西、思考',
    '千夏｜格黑娜｜风纪委员会｜1年级｜手枪｜贯穿｜治疗｜后排｜1星｜原版｜—｜—｜读哲学书',
    '睦月｜格黑娜｜便利屋68｜2年级｜重机枪｜爆发｜输出｜后排｜2星｜原版｜—｜—｜收集炸弹',
    '若藻｜百鬼夜行｜无｜停学中｜狙击枪｜神秘｜输出｜后排｜3星｜原版｜—｜—｜破坏、掠夺',
    '三森｜百鬼夜行｜修行部｜2年级｜手枪｜神秘｜辅助｜中排｜3星｜原版｜—｜—｜少女漫画、做家务',
    '忧｜三一｜图书管理部｜3年级｜狙击枪｜爆发｜辅助｜后排｜3星｜原版｜—｜—｜读书、管理书籍、研究古书',
    '日向｜三一｜修女会｜3年级｜手枪｜神秘｜输出｜中排｜3星｜原版｜—｜—｜祈祷、整理物品',
    '真里奈｜红冬｜红冬秘书处｜2年级｜冲锋枪｜贯穿｜坦克｜前排｜3星｜原版｜—｜—｜散步、突击',
    '宫子｜SRT｜RABBIT小队｜1年级｜冲锋枪｜贯穿｜坦克｜前排｜3星｜原版｜—｜—｜观看宠物视频',
    '美游｜SRT｜RABBIT小队｜1年级｜狙击枪｜贯穿｜辅助｜后排｜3星｜原版｜—｜—｜（消极的）妄想，逃避现实，拣小石子',
    '月咏｜百鬼夜行｜忍术研究部｜1年级｜冲锋枪｜神秘｜坦克｜前排｜3星｜原版｜—｜—｜伪装为树木、屏息',
    '美咲｜阿里乌斯｜阿里乌斯小队｜2年级｜导弹发射器｜爆发｜输出｜后排｜3星｜原版｜—｜—｜独处',
    '亚津子｜阿里乌斯｜阿里乌斯小队｜1年级｜冲锋枪｜爆发｜坦克｜前排｜3星｜原版｜—｜—｜打理花朵',
    '野宫｜阿拜多斯｜对策委员会｜2年级｜重机枪｜贯穿｜输出｜后排｜2星｜原版｜—｜—｜购物',
    '千世｜百鬼夜行｜阴阳部｜2年级｜榴弹发射器｜神秘｜输出｜中排｜2星｜原版｜—｜—｜俳句创作',
    '纱织｜阿里乌斯｜阿里乌斯小队｜2年级｜突击步枪｜爆发｜输出｜中排｜3星｜原版｜—｜—｜无',
    '和纱｜三一｜放学后甜点部｜1年级｜重机枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜“普通地”吃甜点',
    '心奈｜山海经｜梅花园｜1年级｜突击步枪｜贯穿｜治疗｜中排｜3星｜原版｜—｜—｜读童话书',
    '歌原｜千年｜工程部｜3年级｜冲锋枪｜贯穿｜输出｜后排｜2星｜原版｜—｜—｜发明、修理',
    '诺亚｜千年｜研讨会｜2年级｜手枪｜神秘｜辅助｜中排｜3星｜原版｜—｜—｜读书、背诵',
    '优香｜千年｜研讨会｜2年级｜冲锋枪｜爆发｜坦克｜前排｜2星｜原版｜—｜—｜计算',
    '玛丽｜三一｜修女会｜1年级｜手枪｜神秘｜辅助｜后排｜2星｜原版｜—｜—｜祷告、思考',
    '时雨｜红冬｜227号特别班｜2年级｜榴弹发射器｜爆发｜输出｜中排｜3星｜原版｜—｜—｜自制饮品',
    '芹娜｜三一｜救护骑士团｜2年级｜突击步枪｜神秘｜治疗｜后排｜1星｜原版｜—｜—｜看护病人、参加志愿服务',
    '美祢｜三一｜救护骑士团｜3年级｜霰弹枪｜爆发｜坦克｜前排｜3星｜原版｜—｜—｜收集医疗用品',
    '未花｜三一｜茶话会｜3年级｜冲锋枪｜贯穿｜输出｜前排｜3星｜原版｜—｜—｜聊天、收集首饰',
    '惠｜格黑娜｜温泉开发部｜3年级｜喷火器｜爆发｜输出｜前排｜3星｜原版｜—｜—｜拆除',
    '樱子｜三一｜修女会｜3年级｜突击步枪｜神秘｜输出｜中排｜3星｜原版｜—｜—｜祈祷',
    '时｜千年｜C&C｜1年级｜突击步枪｜爆发｜输出｜中排｜3星｜原版｜—｜—｜正在寻找',
    '小雪｜千年｜研讨会｜1年级｜重机枪｜神秘｜输出｜后排｜3星｜原版｜—｜—｜测试运气、逃脱',
    '佳代子｜格黑娜｜便利屋68｜3年级｜手枪｜爆发｜辅助｜中排｜2星｜原版｜—｜—｜收藏音乐CD',
    '果穗｜百鬼夜行｜阴阳部｜3年级｜突击步枪｜神秘｜输出｜中排｜3星｜原版｜—｜—｜宣传百鬼夜行文化、收藏百鬼夜行周边',
    '玲纱｜三一｜三一自警团｜1年级｜霰弹枪｜贯穿｜坦克｜前排｜3星｜原版｜—｜—｜申请决斗、自我介绍',
    '瑠海｜山海经｜玄武商会｜3年级｜冲锋枪｜爆发｜治疗｜前排｜3星｜原版｜—｜—｜料理、食品开发',
    '南｜山海经｜玄龙门｜2年级｜手枪｜爆发｜辅助｜中排｜3星｜原版｜—｜—｜欣赏电影（以冷硬派电影为主）',
    '咲｜SRT｜RABBIT小队｜1年级｜重机枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜保养枪械、采集食物',
    '花子｜三一｜补习部｜2年级｜突击步枪｜贯穿｜治疗｜后排｜2星｜原版｜—｜—｜散步',
    '芽瑠｜红冬｜知识解放战线｜2年级｜手枪｜贯穿｜输出｜中排｜3星｜原版｜—｜—｜画漫画、妄想',
    '琴里｜千年｜工程部｜1年级｜重机枪｜贯穿｜辅助｜后排｜1星｜原版｜—｜—｜聊天',
    '一花｜三一｜正义实现部｜2年级｜突击步枪｜振动｜输出｜中排｜3星｜原版｜—｜—｜帮助他人、尝试各种挑战',
    '霞｜格黑娜｜温泉开发部｜2年级｜手枪｜振动｜输出｜中排｜3星｜原版｜—｜—｜爆破、温泉开发',
    '御坂美琴｜常盘台｜无｜2年级｜突击步枪｜贯穿｜输出｜中排｜3星｜原版｜—｜—｜在便利店里站着看杂志、收集呱太周边',
    '食蜂操祈｜常盘台｜无｜2年级｜手枪｜爆发｜辅助｜中排｜3星｜原版｜—｜—｜喝茶、吃有机食品',
    '紫｜百鬼夜行｜百花缭乱纠纷调解委员会｜1年级｜狙击枪｜振动｜输出｜后排｜3星｜原版｜—｜—｜祈祷、探访零食店',
    '莲华｜百鬼夜行｜百花缭乱纠纷调解委员会｜2年级｜狙击枪｜振动｜输出｜后排｜3星｜原版｜—｜—｜阅读轻小说、锻炼',
    '桔梗｜百鬼夜行｜百花缭乱纠纷调解委员会｜2年级｜狙击枪｜振动｜辅助｜后排｜3星｜原版｜—｜—｜翻花绳、读兵法书、晒太阳',
    '小玉｜千年｜真理部｜3年级｜手枪｜爆发｜辅助｜后排｜1星｜原版｜—｜—｜无线通讯、窃听',
    '晴｜千年｜真理部｜2年级｜突击步枪｜爆发｜辅助｜后排｜2星｜原版｜—｜—｜打游戏、看电影',
    '亚子｜格黑娜｜风纪委员会｜3年级｜手枪｜神秘｜辅助｜后排｜3星｜原版｜—｜—｜日奈',
    '海香｜百鬼夜行｜祭典运营部｜1年级｜突击步枪｜神秘｜输出｜中排｜3星｜原版｜—｜—｜体验庆典、收集庆典周边（手册）',
    '好美｜三一｜放学后甜点部｜1年级｜突击步枪｜贯穿｜输出｜后排｜1星｜原版｜—｜—｜参加活动、收藏限定甜点',
    '绮罗罗｜格黑娜｜闪闪亮亮部｜2年级｜突击步枪｜振动｜输出｜中排｜3星｜原版｜—｜—｜聊天',
    '桃｜千年｜游戏开发部｜1年级｜突击步枪｜贯穿｜输出｜中排｜2星｜原版｜—｜—｜游戏',
    '康娜｜瓦尔基里｜公共安全局｜3年级｜手枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜读书、鉴赏电影（推理片）',
    '萌绘｜SRT｜RABBIT小队｜1年级｜手枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜烟花',
    '日和｜阿里乌斯｜阿里乌斯小队｜2年级｜狙击枪｜爆发｜辅助｜后排｜3星｜原版｜—｜—｜收集杂志',
    '丽情｜山海经｜玄武商会｜3年级｜突击步枪｜神秘｜辅助｜中排｜3星｜原版｜—｜—｜练习功夫、美食',
    '千明｜格黑娜｜万魔殿｜2年级｜突击步枪｜振动｜输出｜中排｜3星｜原版｜—｜—｜发行周刊、交朋友',
    '圣娅｜三一｜茶话会｜3年级｜手枪｜贯穿｜辅助｜中排｜3星｜原版｜—｜—｜解谜、阅读',
    '濑名｜格黑娜｜急救医学部｜3年级｜榴弹发射器｜神秘｜载具支援｜后排｜3星｜原版｜—｜—｜待命、清点药品',
    '朱莉｜格黑娜｜供餐部｜1年级｜霰弹枪｜爆发｜辅助｜后排｜1星｜原版｜—｜—｜烹饪研究',
    '光｜海兰德｜CCC｜1年级｜手枪｜振动｜辅助｜中排｜3星｜原版｜—｜—｜（奇怪的）驾驶练习、观察蚂蚁',
    '望｜海兰德｜CCC｜1年级｜手枪｜振动｜输出｜中排｜3星｜原版｜—｜—｜刷新最快纪录',
    '名草｜百鬼夜行｜百花缭乱纠纷调解委员会｜3年级｜狙击枪｜振动｜输出｜后排｜3星｜原版｜—｜—｜冥想、阅读',
    '莲见｜三一｜正义实现部｜3年级｜狙击枪｜贯穿｜输出｜后排｜2星｜原版｜—｜—｜读书、观察人类',
    '庚｜狂猎｜神秘学研究会（第4宿舍404室）｜3年级｜霰弹枪｜神秘｜坦克｜前排｜3星｜原版｜—｜—｜妄想',
    '美代｜狂猎｜特殊交易部（第5宿舍402室）｜2年级｜狙击枪｜振动｜辅助｜后排｜3星｜原版｜—｜—｜收集打字机',
    '冬｜狂猎｜特殊交易部（第5宿舍402室）｜2年级｜手枪｜振动｜辅助｜中排｜3星｜原版｜—｜—｜收看电视、改造家电',
    '铃美｜三一｜三一自警团｜2年级｜突击步枪｜爆发｜辅助｜中排｜1星｜原版｜—｜—｜巡逻、散步',
    '昴｜阿里乌斯｜尼科米底亚部队｜3年级｜突击步枪｜神秘｜输出｜中排｜3星｜原版｜—｜—｜演奏口琴',
    '贵音｜红冬｜出版部｜2年级｜手枪｜神秘｜治疗｜中排｜3星｜原版｜—｜—｜阅读、拍照、观看冰球',
    '莉音｜千年｜研讨会｜3年级｜手枪｜神秘｜辅助｜后排｜3星｜原版｜—｜—｜设计',
    '柯伊｜千年｜超自然现象研究部｜1年级｜轨道炮｜神秘｜辅助｜后排｜3星｜原版｜—｜—｜照顾爱丽丝、打扮、游戏（本人对此否认）',
    '蕾娜｜狂猎｜神秘学研究会（第4宿舍404室）｜1年级｜手枪｜爆发｜辅助｜中排｜3星｜原版｜—｜—｜制作服装/饰品',
    '妮可｜SRT｜FOX小队｜3年级｜霰弹枪｜爆发｜辅助｜前排｜3星｜原版｜—｜—｜烹饪（尤其是稻荷寿司）',
    '胡桃｜SRT｜FOX小队｜3年级｜冲锋枪｜爆发｜坦克｜前排｜3星｜原版｜—｜—｜收集贴纸、打扫',
    '春香｜格黑娜｜便利屋68｜1年级｜霰弹枪｜爆发｜坦克｜前排｜1星｜原版｜—｜—｜培育杂草',
    '雪玲｜山海经｜梅花园｜绝密｜狙击枪｜振动｜输出｜后排｜3星｜原版｜—｜—｜吃甜食',
    '妃咲｜山海经｜玄龙门｜3年级｜冲锋枪｜振动｜辅助｜后排｜3星｜原版｜—｜—｜茶道、私访',
    '真琴｜格黑娜｜万魔殿｜3年级｜狙击枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜搞阴谋诡计、陪伊吹玩',
    '皋月｜格黑娜｜万魔殿｜3年级｜手枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜催眠研究、购物',
    '伊吕波｜格黑娜｜万魔殿｜2年级｜手枪｜神秘｜载具支援｜后排｜3星｜原版｜—｜—｜读书，偷懒',
    '心｜奥德赛｜潜水部｜2年级｜突击步枪｜神秘｜辅助｜中排｜3星｜原版｜—｜—｜潜水、烹饪、（独自）唱歌',
    '琴音｜奥德赛｜潜水部｜2年级｜突击步枪｜爆发｜坦克｜前排｜3星｜原版｜—｜—｜潜水、阅读、无线电通信',
    '安娜｜红冬｜183号特别班｜2年级｜手枪｜贯穿｜输出｜中排｜3星｜原版｜—｜—｜回收、制作奖状框',
    '茜｜千年｜C&C｜2年级｜手枪｜贯穿｜辅助｜中排｜2星｜原版｜—｜—｜清洁',
    '明里｜格黑娜｜美食研究会｜3年级｜突击步枪｜爆发｜输出｜中排｜2星｜原版｜—｜—｜暴饮暴食',
    '纯子｜格黑娜｜美食研究会｜1年级｜突击步枪｜贯穿｜输出｜中排｜2星｜原版｜—｜—｜美食探店',
    '芹香｜阿拜多斯｜对策委员会｜1年级｜突击步枪｜爆发｜输出｜中排｜2星｜原版｜—｜—｜攒钱、打工',
    '椿｜百鬼夜行｜修行部｜2年级｜冲锋枪｜贯穿｜坦克｜前排｜2星｜原版｜—｜—｜睡午觉',
    '桐乃｜瓦尔基里｜生活安全局｜1年级｜手枪｜爆发｜辅助｜中排｜2星｜原版｜—｜—｜美食探店',
    '红叶｜红冬｜知识解放战线｜1年级｜导弹发射器｜振动｜输出｜后排｜2星｜原版｜—｜—｜收集漫画书',
    '菲娜｜百鬼夜行｜祭典运营部｜1年级｜重机枪｜贯穿｜输出｜后排｜1星｜原版｜—｜—｜欣赏任侠电影',
    '巴｜红冬｜红冬秘书处｜3年级｜狙击枪｜贯穿｜辅助｜后排｜1星｜原版｜—｜—｜煽动',
    '吹雪｜瓦尔基里｜生活安全局｜1年级｜狙击枪｜贯穿｜输出｜后排｜1星｜原版｜—｜—｜填字游戏、听广播',
    '满｜百鬼夜行｜忍术研究部｜3年级｜霰弹枪｜神秘｜输出｜前排｜1星｜原版｜—｜—｜开发新的自创忍术，拍摄视频',
    '响｜千年｜工程部｜1年级｜迫击炮｜爆发｜输出｜后排｜3星｜原版｜—｜—｜cosplay、购物',
    '伊吹｜格黑娜｜万魔殿｜1年级｜突击步枪｜神秘｜辅助｜中排｜1星｜原版｜—｜—｜预习、复习、收集玩偶',
    '爱理｜三一｜放学后甜点部｜1年级｜冲锋枪｜爆发｜辅助｜后排｜2星｜原版｜—｜—｜探访甜品店、参加茶会',
    '青叶｜海兰德｜货运管理部｜2年级｜霰弹枪｜振动｜坦克｜前排｜1星｜原版｜—｜—｜妄想、若无其事地毒舌发言',
    '兰舞｜三一｜无｜辍学｜霰弹枪｜振动｜输出｜前排｜1星｜原版｜—｜—｜擦拭头盔、搜刮自动贩卖机底下',
    '御伽｜SRT｜FOX小队｜3年级｜狙击枪｜爆发｜输出｜后排｜1星｜原版｜—｜—｜解谜、空想',
    '纱绫｜山海经｜炼丹研究会｜2年级｜手枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜做研究',
    '真白｜三一｜正义实现部｜1年级｜狙击枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜登高、写观察日记',
    '初音未来｜联动｜无｜其他｜榴弹发射器｜—｜—｜—｜3星｜原版｜青发｜—｜唱歌、跳舞',
    '和香｜红冬｜227号特别班｜2年级｜冲锋枪｜爆发｜辅助｜后排｜1星｜原版｜—｜—｜天文观测',
    '千寻｜千年｜真理部｜3年级｜突击步枪｜贯穿｜输出｜后排｜3星｜原版｜—｜—｜购买电子设备',
    '枫｜百鬼夜行｜修行部｜1年级｜手枪｜爆发｜辅助｜后排｜3星｜原版｜—｜—｜恶作剧（尽可能忍耐中）,抓独角仙',
    '日鞠｜千年｜超自然现象研究部｜3年级｜手枪｜贯穿｜辅助｜后排｜3星｜原版｜—｜—｜查看今日运势、一切超自然现象',
    '花江｜三一｜救护骑士团｜1年级｜突击步枪｜爆发｜治疗｜后排｜2星｜原版｜—｜—｜跳舞、拉拉队',
    '风香｜格黑娜｜供餐部｜2年级｜冲锋枪｜爆发｜治疗｜后排｜2星｜原版｜—｜—｜烹饪、做便当',
    '渚｜三一｜茶话会｜3年级｜手枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜收集茶叶、制作点心、打理庭院',
    '实梨｜红冬｜工务部｜3年级｜突击步枪｜爆发｜输出｜后排｜3星｜原版｜—｜—｜罢工、抗议、施工',
    '尼娅｜百鬼夜行｜阴阳部｜3年级｜手枪｜振动｜输出｜后排｜3星｜原版｜—｜—｜疼爱后辈、密谋',
    '律｜狂猎｜特殊交易部（第5宿舍402室）｜1年级｜冲锋枪｜神秘｜辅助｜后排｜3星｜原版｜—｜—｜走私、采石',
    '八云｜红冬｜出版部｜3年级｜手枪｜爆发｜辅助｜后排｜3星｜原版｜—｜—｜制订事业企划、分析铁路路线',
    '绘梨香｜格黑娜｜闪闪亮亮部｜2年级｜霰弹枪｜振动｜辅助｜后排｜3星｜原版｜—｜—｜橱窗购物、收集商品目录',
    '绫音｜阿拜多斯｜对策委员会｜1年级｜手枪｜贯穿｜治疗｜后排｜2星｜原版｜—｜—｜记账、收集古董',
    '静子｜百鬼夜行｜祭典运营部｜2年级｜霰弹枪｜神秘｜辅助｜后排｜2星｜原版｜—｜—｜扮可爱迎客、看板娘拳',
    '志美子｜三一｜图书管理部｜1年级｜突击步枪｜爆发｜辅助｜后排｜1星｜原版｜—｜—｜读书、制作书签',
    '佐天泪子｜佐贺川｜无｜1年级｜冲锋枪｜贯穿｜输出｜后排｜1星｜原版｜—｜—｜在网上打麻将、调查各种甜点',
    '阿罗娜｜夏莱｜无｜其他｜无武器｜—｜—｜—｜1星｜原版｜蓝发｜蓝色恶魔｜管理什亭之匣',
    '普拉娜｜夏莱｜无｜其他｜无武器｜—｜—｜—｜1星｜原版｜白发｜—｜待机、观察老师',
)

PROFILES: dict[str, dict[str, str]] = {}
for _line in ATTRIBUTES:
    _p = _line.split("｜")
    if len(_p) >= 7:
        PROFILES[_p[0]] = {
            "school": _p[1],
            "club": _p[2],
            "year": _p[3],
            "weapon": _p[4],
            "atk": _p[5],
            "role": _p[6],
            "pos": _p[7],
            "star": _p[8],
            "form": _p[9],
            "hair": _p[10],
            "nick": _p[11],
            "hobby": _p[12],
        }

LONG_NAMES: tuple[str, ...] = tuple(n for n in NAMES if len(n) >= 2)
FORM_BASE = "原版"
COSTUME_NAMES: tuple[str, ...] = tuple(
    n for n, p in PROFILES.items() if p.get("form") and p["form"] != FORM_BASE
)
ALL_NAMES: tuple[str, ...] = tuple(NAMES) + COSTUME_NAMES
FORM_VALUES: tuple[str, ...] = tuple(
    {p.get("form", "") for p in PROFILES.values() if p.get("form") and p["form"] != FORM_BASE}
)


CLUBS: dict[str, tuple[str, ...]] = {
    '对策委员会': ('星野', '白子', '野宫', '芹香', '绫音'),
    'C&C': ('妮露', '卡琳', '明日奈', '时', '茜'),
    '万魔殿': ('千明', '真琴', '皋月', '伊吕波', '伊吹'),
    '便利屋68': ('阿露', '睦月', '佳代子', '春香'),
    '美食研究会': ('晴奈', '泉', '明里', '纯子'),
    '补习部': ('日富美', '梓', '小春', '花子'),
    '风纪委员会': ('日奈', '伊织', '千夏', '亚子'),
    '真理部': ('真纪', '小玉', '晴', '千寻'),
    '正义实现部': ('鹤城', '一花', '莲见', '真白'),
    '游戏开发部': ('爱丽丝', '绿', '柚子', '桃'),
    '放学后甜点部': ('夏', '和纱', '好美', '爱理'),
    'RABBIT小队': ('宫子', '美游', '咲', '萌绘'),
    '阿里乌斯小队': ('美咲', '亚津子', '纱织', '日和'),
    '研讨会': ('诺亚', '优香', '小雪', '莉音'),
    '百花缭乱纠纷调解委员会': ('紫', '莲华', '桔梗', '名草'),
    '超自然现象研究部': ('艾米', '柯伊', '日鞠'),
    '梅花园': ('瞬', '心奈', '雪玲'),
    '忍术研究部': ('泉奈', '月咏', '满'),
    '红冬秘书处': ('切里诺', '真里奈', '巴'),
    '修行部': ('三森', '椿', '枫'),
    '修女会': ('日向', '玛丽', '樱子'),
    '阴阳部': ('千世', '果穗', '尼娅'),
    '工程部': ('歌原', '琴里', '响'),
    '救护骑士团': ('芹娜', '美祢', '花江'),
    '茶话会': ('未花', '圣娅', '渚'),
    '祭典运营部': ('海香', '菲娜', '静子'),
    '特殊交易部（第5宿舍402室）': ('美代', '冬', '律'),
    'FOX小队': ('妮可', '胡桃', '御伽'),
    '图书管理部': ('忧', '志美子'),
    '227号特别班': ('时雨', '和香'),
    '温泉开发部': ('惠', '霞'),
    '三一自警团': ('玲纱', '铃美'),
    '玄武商会': ('瑠海', '丽情'),
    '玄龙门': ('南', '妃咲'),
    '知识解放战线': ('芽瑠', '红叶'),
    '闪闪亮亮部': ('绮罗罗', '绘梨香'),
    '供餐部': ('朱莉', '风香'),
    'CCC': ('光', '望'),
    '神秘学研究会（第4宿舍404室）': ('庚', '蕾娜'),
    '出版部': ('贵音', '八云'),
    '潜水部': ('心', '琴音'),
    '生活安全局': ('桐乃', '吹雪'),
    '健身部': ('堇',),
    '公共安全局': ('康娜',),
    '急救医学部': ('濑名',),
    '尼科米底亚部队': ('昴',),
    '183号特别班': ('安娜',),
    '货运管理部': ('青叶',),
    '炼丹研究会': ('纱绫',),
    '工务部': ('实梨',),
}

PROMPT_SYSTEM = """你在主持《碧蓝档案》学生猜谜游戏（类似 Akinator）。
老师心里想的是下面名单里的某一位学生（名单为角色名，不含服装版本）。

碧蓝档案常识（提问前必须遵守）：
- 所有学生都是持枪的基沃托斯学生，禁止问「是不是枪械」「是不是学生」「是不是女的」这种人人一样的属性。
- 武器只能问种类：狙击枪 / 霰弹枪 / 机枪 / 冲锋枪 / 步枪 / 手枪 / 特殊武器。
- 有效角度：学校、社团、年级、年龄、武器种类、战术定位、站位、爱好、所属组织、剧情关系、是否联动。
- 禁止问身高、发色、瞳色、兽耳：档案里没有这些数据，问了也没法判断。

提问规则：
1. 每次只问一个问题，必须能用「是 / 不是」回答。
2. 每问一个问题都要明显缩小范围，至少砍掉一部分候选。
3. 严禁问名字，严禁把候选名字写进问题。
4. 不要重复已问过的问题，也不要重新猜已排除的名字。
5. 至少问满 6 个问题才允许 GUESS；不足 6 问只能继续 ASK。
6. 问得越少猜中越厉害，但宁可多问也不要瞎猜。
7. 同一个条件只问一次；某一项已经回答「是」后，禁止再问同类的其他取值（例：已确认是补习部，就不要再问是不是研讨会；已确认是三年级，就不要再问是不是二年级）。
7.1 年级和年龄必须用固定问法：「她是 X 年级吗？」「她是 X 岁吗？」，禁止「高年级」「年纪大」这类模糊说法。
8. GUESS 的学生必须同时满足所有回答「是」的条件；与任何一条「是」冲突就不能猜。
9. 尽量覆盖多个不同维度（学校 / 社团 / 年级 / 年龄 / 武器 / 定位 / 站位 / 爱好 / 剧情）。
9.1 优先用并集问法做二分：「她的学校是千年、格黑娜、三一之一吗？」，一次排除一半；同一字段确认「是」后不要再问该字段。

输出格式（只输出一种，不要解释）：
ASK: <一个问题，不超过 30 字>
或
GUESS: <学生名，必须严格来自名单>
"""


DIM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "学校": ("学校", "学园", "学院", "格黑娜", "千年", "三一", "阿拜多斯", "百鬼", "红冬",
             "山海经", "阿里乌斯", "瓦尔基里", "SRT", "常盘台", "狂猎", "海兰德", "奥德赛",
             "千禧年", "崔尼蒂", "歌赫娜", "海兰德", "狂猎艺术学院"),
    "定位": ("输出", "坦克", "治疗", "奶妈", "辅助", "支援", "载具", "定位"),
    "站位": ("前排", "中排", "后排", "站位"),
    "社团": ("社团", "部员", "部活", "委员会", "便利屋", "风纪", "游戏开发", "C&C", "研讨会",
             "茶会", "修女会", "忍术", "修行", "对策", "自警团", "供给部", "美食研究会"),
    "外貌": ("发色", "头发", "发型", "马尾", "双马尾", "眼镜", "身高", "身材", "耳朵", "尾巴",
             "角", "瞳", "眼睛", "帽子", "发带", "服装", "翅膀", "光环"),
    "性格": ("性格", "说话", "语气", "口头禅", "喜欢", "讨厌", "懒", "认真", "怕", "活泼", "安静"),
    "武器": ("狙击", "霰弹", "机枪", "冲锋枪", "步枪", "手枪", "刀", "盾", "炮", "武器种类"),
    "剧情": ("剧情", "主线", "所属", "关系", "阵营", "联动", "加入", "以前", "曾经"),
}

def _dim_of(q: str) -> str:
    """把问题归类到某个维度，无法归类返回空串。"""
    best = ""
    for dim, words in DIM_KEYWORDS.items():
        if any(w in q for w in words):
            if not best or len(dim) < len(best):
                best = dim
    return best


def _dim_counts(history: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in history or []:
        q = str(item.get('q', ''))
        for dim, words in DIM_KEYWORDS.items():
            if any(w in q for w in words):
                counts[dim] = counts.get(dim, 0) + 1
                break
    return counts



CLUB_ALIAS: dict[str, str] = {
    "姐妹会": "修女会",
    "崔尼蒂自警团": "三一自警团",
    "阿里乌斯战术小队": "阿里乌斯小队",
    "甜点部": "放学后甜点部",
    "真理社": "真理部",
    "庆典运营管理部": "祭典运营部",
    "红冬事务局": "红冬秘书处",
    "超自然现象调查部": "超自然现象研究部",
}
SCHOOL_ALIAS: dict[str, str] = {
    "千禧年": "千年",
    "崔尼蒂": "三一",
    "歌赫娜": "格黑娜",
    "瓦尔基丽": "瓦尔基里",
    "栅川": "佐贺川",
    "常盘台中学": "常盘台",
    "阿拜多斯高等学院": "阿拜多斯",
}
WEAPON_NAMES: tuple[str, ...] = (
    "狙击枪", "霰弹枪", "重机枪", "机枪", "冲锋枪", "突击步枪", "步枪", "手枪",
    "榴弹发射器", "导弹发射器", "火箭筒", "轨道炮", "电磁炮", "迫击炮", "喷火器",
)
ATK_NAMES: tuple[str, ...] = ("爆发", "贯穿", "神秘", "振动")
ROLE_WORDS: dict[str, str] = {
    "载具支援": "载具支援", "输出": "输出", "坦克": "坦克", "治疗": "治疗",
    "奶妈": "治疗", "辅助": "辅助", "支援": "辅助", "载具": "载具支援",
}
POS_WORDS: tuple[str, ...] = ("前排", "中排", "后排")
YEAR_MAP = {"一": "1年级", "二": "2年级", "三": "3年级",
            "1": "1年级", "2": "2年级", "3": "3年级"}
STAR_MAP = {"一": "1星", "二": "2星", "三": "3星",
            "1": "1星", "2": "2星", "3": "3星"}

HOBBY_TOKENS: set[str] = set()
NICK_VALUES: tuple[str, ...] = tuple(
    {p.get("nick", "") for p in PROFILES.values() if p.get("nick") not in ("", "—", None)}
)
HAIR_VALUES: tuple[str, ...] = tuple(
    {p.get("hair", "") for p in PROFILES.values() if p.get("hair") not in ("", "—", None)}
)
for _p in PROFILES.values():
    for _tok in re.split(r"[、，,/（）()\s]+", _p.get("hobby", "")):
        if len(_tok) >= 2:
            HOBBY_TOKENS.add(_tok)


def _mentioned(q: str, canonical: tuple[str, ...], alias: dict[str, str]) -> set[str]:
    hits: set[str] = set()
    for c in canonical:
        if c and c in q:
            hits.add(c)
    for a, c in alias.items():
        if a in q:
            hits.add(c)
    # 去掉被更长名称包含的短词（突击步枪 里不要再认出 步枪）
    return {h for h in hits if not any(h != o and h in o for o in hits)}


def _conditions(q: str) -> list[tuple[str, str]]:
    """从问题里提取可校验的条件。"""
    out: list[tuple[str, str]] = []
    schools = tuple({p["school"] for p in PROFILES.values()})
    club_hits = _mentioned(q, tuple(CLUBS.keys()), CLUB_ALIAS)
    for v in club_hits:
        out.append(("club", v))
    # 先把社团名从问句里抹掉，避免「红冬秘书处」被当成学校「红冬」
    q2 = q
    for c in sorted(club_hits, key=len, reverse=True):
        q2 = q2.replace(c, "□")
    for v in _mentioned(q2, schools, SCHOOL_ALIAS):
        out.append(("school", v))
    for v in _mentioned(q2, WEAPON_NAMES, {}):
        out.append(("weapon", v))
    for v in _mentioned(q2, ATK_NAMES, {}):
        out.append(("atk", v))
    q = q2
    for m in re.finditer(r"([一二三1-3])\s*星", q):
        out.append(("star", STAR_MAP.get(m.group(1), "")))
    for m in re.finditer(r"([一二三1-3])\s*年级", q):
        out.append(("year", YEAR_MAP.get(m.group(1), "")))
    role_hits = [w for w in ROLE_WORDS if w in q]
    role_hits.sort(key=len, reverse=True)
    picked: list[str] = []
    for w in role_hits:
        if any(w in p for p in picked):
            continue
        picked.append(w)
    for w in picked:
        out.append(("role", ROLE_WORDS[w]))
    for p in POS_WORDS:
        if p in q:
            out.append(("pos", p))
    for v in _mentioned(q, NICK_VALUES, {}):
        out.append(("nick", v))
    if re.search(r"形态|服装|版本|皮肤|造型", q):
        for v in _mentioned(q, FORM_VALUES, {}):
            out.append(("form", v))
    for v in _mentioned(q, HAIR_VALUES, {}):
        out.append(("hair", v))
    if re.search(r"喜欢|爱好|兴趣", q) and any(tok in q for tok in HOBBY_TOKENS):
        out.append(("hobby", q))
    return [(f, v) for f, v in out if v]


def _hobby_hit(prof: dict, q: str) -> bool:
    hobby = str(prof.get("hobby", ""))
    for tok in re.split(r"[、，,/（）()\s]+", hobby):
        if len(tok) >= 2 and tok in q:
            return True
    return False


def _cond_groups(q: str) -> tuple[dict[str, set[str]], set[str]]:
    """把问题解析成「字段 → 取值集合」，支持「A、B、C 之一」的并集问法。"""
    groups: dict[str, set[str]] = {}
    tokens: set[str] = set()
    for field, value in _conditions(q):
        if field == "hobby":
            tokens.add(field)
            continue
        groups.setdefault(field, set()).add(value)
    return groups, tokens


def _token_hit(prof: dict, field: str, q: str) -> bool:
    text = str(prof.get(field, "") or "")
    for tok in re.split(r"[、，,/（）()\s]+", text):
        if len(tok) >= 2 and tok in q:
            return True
    return False


def _cond_hit(prof: dict, field: str, value: str, q: str) -> bool:
    if field == "hobby":
        return _token_hit(prof, field, q)
    return prof.get(field, "") == value


def _candidates(
    history: list[dict], excluded: list[str], pool: tuple[str, ...] | None = None
) -> list[str]:
    """按已答条件筛出所有可能的候选（支持并集问法）。"""
    names = pool or NAMES
    out: list[str] = []
    for name in names:
        prof = PROFILES.get(name) or {}
        if name in (excluded or []):
            continue
        ok = True
        for item in history or []:
            q = str(item.get("q", ""))
            ans = str(item.get("a", ""))
            if ans not in ("是", "不是"):
                continue
            groups, tokens = _cond_groups(q)
            for field, values in groups.items():
                inside = prof.get(field, "") in values
                if ans == "是" and not inside:
                    ok = False
                if ans == "不是" and inside:
                    ok = False
            for field in tokens:
                hit = _token_hit(prof, field, q)
                if ans == "是" and not hit:
                    ok = False
                if ans == "不是" and hit:
                    ok = False
            if not ok:
                break
        if ok:
            out.append(name)
    return out


def _violations(name: str, history: list[dict]) -> str:
    """检查猜测是否与已答的「是 / 不是」冲突（支持并集问法）。"""
    prof = PROFILES.get(name)
    if not prof:
        return ""
    for item in history or []:
        q = str(item.get("q", ""))
        ans = str(item.get("a", ""))
        if ans not in ("是", "不是"):
            continue
        groups, tokens = _cond_groups(q)
        for field, values in groups.items():
            inside = prof.get(field, "") in values
            if ans == "是" and not inside:
                return f"回答「是」的「{'/'.join(sorted(values))}」与 {name} 的{field}冲突"
            if ans == "不是" and inside:
                return f"回答「不是」的「{'/'.join(sorted(values))}」与 {name} 的{field}冲突"
        for field in tokens:
            hit = _token_hit(prof, field, q)
            if ans == "是" and not hit:
                return f"回答「是」的{field}条件与 {name} 的{field}冲突"
            if ans == "不是" and hit:
                return f"回答「不是」的{field}条件与 {name} 的{field}冲突"
    return ""


FIELD_LABEL = {
    "school": "学校",
    "club": "社团",
    "weapon": "武器",
    "atk": "攻击类型",
    "role": "定位",
    "pos": "站位",
    "year": "年级",
    "star": "稀有度",
    "hair": "发色",
    "nick": "昵称",
    "form": "形态",
}


def _answered_sets(history: list[dict]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """整理已答的「是 / 不是」取值集合。"""
    yes_vals: dict[str, set[str]] = {}
    no_vals: dict[str, set[str]] = {}
    for item in history or []:
        groups, _ = _cond_groups(str(item.get("q", "")))
        ans = str(item.get("a", ""))
        for field, values in groups.items():
            if ans == "是":
                yes_vals.setdefault(field, set()).update(values)
            elif ans == "不是":
                no_vals.setdefault(field, set()).update(values)
    return yes_vals, no_vals


def _best_split(
    history: list[dict], excluded: list[str], pool: tuple[str, ...] | None = None
) -> tuple[str, list[str]] | None:
    """在当前候选里找一个把人劈成两半的问题（字段 + 最多 4 个取值）。"""
    from collections import Counter
    from itertools import combinations

    cands = _candidates(history, excluded, pool)
    total = len(cands)
    if total < 3:
        return None
    yes_vals, no_vals = _answered_sets(history)
    half = total / 2
    best: tuple[float, str, list[str]] | None = None

    asked_pairs: set[tuple[str, frozenset[str]]] = set()
    asked_vals: set[tuple[str, str]] = set()
    for item in history or []:
        groups, _ = _cond_groups(str(item.get("q", "")))
        for field, values in groups.items():
            asked_pairs.add((field, frozenset(values)))
            for v in values:
                asked_vals.add((field, v))

    for field in ("form", "school", "club", "weapon", "atk", "role", "pos", "year",
                  "star", "hair", "nick"):
        counts = Counter(PROFILES[c].get(field, "") for c in cands)
        values = [v for v, n in counts.items() if v and v not in ("—", "无")]
        if field in yes_vals:
            if field == "form":
                # 形态用于区分服装版，允许在已确认范围内继续二分
                values = [v for v in values if v in yes_vals[field]]
            else:
                # 其余字段确认后不再提问
                continue
        blocked = no_vals.get(field, set())
        values = [v for v in values if v not in blocked]
        values = [v for v in values if (field, v) not in asked_vals]
        if len(values) < 2:
            continue
        values.sort(key=lambda v: counts[v], reverse=True)
        max_k = min(4, len(values) - 1)
        for k in range(1, max_k + 1):
            for subset in combinations(values, k):
                if (field, frozenset(subset)) in asked_pairs:
                    continue
                size = sum(counts[v] for v in subset)
                if size == 0 or size == total:
                    continue
                score = abs(size - half) + 0.6 * k
                if best is None or score < best[0]:
                    best = (score, field, list(subset))
    if not best:
        return None
    return best[1], best[2]


def _split_question(field: str, values: list[str]) -> str:
    label = FIELD_LABEL.get(field, field)
    if len(values) == 1:
        return f"她的{label}是{values[0]}吗？"
    joined = "、".join(values)
    return f"她的{label}是{joined}之一吗？"



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

    @staticmethod
    def _fallback_candidate(
        history: list[dict], excluded: list[str], pool: tuple[str, ...] | None = None
    ) -> str:
        """按已答条件筛一个候选（含别名）。"""
        cands = _candidates(history, excluded, pool)
        return cands[0] if cands else ""

    async def _phrase(self, canonical: str, values: list[str]) -> str:
        """让模型把代码选好的问题润色成自然问句，失败则返回空串。"""
        system = (
            "你是提问改写器。把用户给出的是非题改写成自然、口语化的中文问句，"
            "必须原样保留其中的人物或团体名称，不能添加新条件，只输出问句本身。"
        )
        try:
            timeout = float(self.config.get("timeout", 45) or 45)
            if str(self.config.get("api_key", "") or "").strip():
                text = await asyncio.wait_for(
                    self._direct_chat(system, canonical), timeout=timeout
                )
            else:
                provider = self.context.get_using_provider()
                if provider is None:
                    return ""
                resp = await asyncio.wait_for(
                    provider.text_chat(
                        prompt=canonical, system_prompt=system, contexts=[]
                    ),
                    timeout=timeout,
                )
                text = getattr(resp, "completion_text", "") or ""
            text = (text or "").strip()
            if not text:
                return ""
            text = text.splitlines()[0].strip().strip("「」\"' ")
            if len(text) < 6 or "吗" not in text:
                return ""
            if any(n in text for n in LONG_NAMES):
                return ""
            if not any(v in text for v in values):
                return ""
            return text[:60]
        except Exception as exc:
            logger.info(f"[BA20Q] 润色失败，改用原句：{exc}")
            return ""

    async def _ask_ai(self, sess: dict) -> tuple[str, str]:
        provider = None
        if not str(self.config.get("api_key", "") or "").strip():
            provider = self.context.get_using_provider()

        max_q = int(
            self.config.get("max_questions", MAX_QUESTIONS_DEFAULT)
            or MAX_QUESTIONS_DEFAULT
        )
        calls = int(sess.get("calls", 0) or 0) + 1
        sess["calls"] = calls
        history = sess.get("history") or []
        excluded = sess.get("excluded") or []
        pool = tuple(sess.get("pool") or NAMES)
        q_count = int(sess.get("q_count", 0) or 0)
        force_guess = q_count >= max_q or calls > max_q * 2
        hist_text = "\n".join(f"{i + 1}. {h['q']} → {h['a']}" for i, h in enumerate(history)) or "（还没有）"
        prompt = (
            f"别名对照：\n{self._alias_hint()}\n\n"
            "正式校名：千年科技学院、格黑娜学院、崔尼蒂综合学院、海兰德铁道学院、狂猎艺术学院、瓦尔基里警员学院、阿拜多斯高等学院。\n\n"
            "角色档案（名字｜学校｜社团｜学年｜武器｜攻击类型｜定位｜站位｜稀有度｜发色｜昵称｜爱好）：\n"
            + "\n".join(ATTRIBUTES)
            + "\n\n"
            f"已问过的问题与回答：\n{hist_text}\n\n"
            f"已经猜错、必须排除的名字：{'、'.join(excluded) if excluded else '（无）'}\n\n"
            + (
                "已覆盖维度："
                + ("、".join(f"{k}{v}次" for k, v in _dim_counts(history).items()) or "（还没有）")
                + "。学校和社团各最多 2 次，多问外貌、性格、特征。\n\n"
            )
            + (
                f"开局要求：第一个问题请从「{sess.get('opening', '学校')}」切入，别每次都问学校。\n\n"
                if not history
                else ""
            )
            + (
                "当前候选人数："
                + str(len(_candidates(history, excluded, pool)))
                + (
                    "（" + "、".join(_candidates(history, excluded, pool)[:12]) + "）"
                    if 0 < len(_candidates(history, excluded, pool)) <= 12
                    else ""
                )
                + "。下一问必须让候选数至少减半。\n"
            )
            + (
                "已确认、禁止再问的字段："
                + "、".join(
                    FIELD_LABEL.get(f, f)
                    for f in _answered_sets(history)[0]
                    if f != "hobby"
                )
                + "。\n"
                if _answered_sets(history)[0]
                else ""
            )
            + f"已问 {q_count} 个问题，本局最多 {max_q} 问。"
            + (
                "已经问满，必须直接输出 GUESS，禁止再提问，也不要解释。\n"
                if force_guess
                else (
                    f"还没问满 {MIN_QUESTIONS} 问，禁止 GUESS，只能 ASK。\n"
                    if q_count < MIN_QUESTIONS
                    else "可以继续 ASK，也可以 GUESS。\n"
                )
            )
            + "请输出 ASK 或 GUESS。"
        )

        _cands = _candidates(history, excluded, pool)
        if len(_cands) == 1 and q_count >= MIN_QUESTIONS:
            logger.info(f"[BA20Q] 候选只剩 1 人，直接作答：{_cands[0]}")
            return "guess", _cands[0]

        # 代码选最优二分问题，模型只负责润色措辞
        split = _best_split(history, excluded, pool)
        if split and not force_guess:
            field, values = split
            canonical = _split_question(field, values)
            phrased = await self._phrase(canonical, values)
            sess["q_count"] = q_count + 1
            sess["canonical"] = canonical
            question = phrased or canonical
            logger.info(f"[BA20Q] 二分提问：{question}（{field}={values}）")
            return "ask", question
        if split is None and _cands and q_count >= MIN_QUESTIONS:
            logger.info(f"[BA20Q] 无可用问题，直接作答：{_cands[0]}（候选 {len(_cands)}）")
            return "guess", _cands[0]

        last_error = "未知错误"
        last_kind, last_value = "", ""
        rejected_height = False
        rejected_name = False
        rejected_guess = False
        rejected_force = False
        rejected_dim = False
        for attempt in range(2):
            try:
                sys_prompt = PROMPT_SYSTEM.format(max_q=max_q)
                if provider is not None:
                    resp = await asyncio.wait_for(
                        provider.text_chat(
                            prompt=prompt, system_prompt=sys_prompt, contexts=[]
                        ),
                        timeout=float(self.config.get("timeout", 45) or 45),
                    )
                    text = (getattr(resp, "completion_text", "") or "").strip()
                else:
                    if not str(self.config.get("api_key", "") or "").strip():
                        return "error", "当前没有可用的对话模型"
                    text = await self._direct_chat(sys_prompt, prompt)
                kind, value = self._parse_reply(text)
                if kind:
                    if kind == "ask":
                        yes_vals: dict[str, set[str]] = {}
                        no_vals: dict[str, set[str]] = {}
                        for _h in history:
                            _g, _ = _cond_groups(str(_h.get("q", "")))
                            _ans = str(_h.get("a", ""))
                            for _f, _vs in _g.items():
                                if _ans == "是":
                                    yes_vals.setdefault(_f, set()).update(_vs)
                                elif _ans == "不是":
                                    no_vals.setdefault(_f, set()).update(_vs)
                        new_groups, new_tokens = _cond_groups(value)
                        bad = ""
                        for _f, _vs in new_groups.items():
                            if _f in yes_vals:
                                if _f == "form" and _vs <= yes_vals[_f] and _vs != yes_vals[_f]:
                                    pass
                                else:
                                    bad = (
                                        f"已经确认过{_f}"
                                        f"（{'/'.join(sorted(yes_vals[_f]))}），"
                                        f"不要再问{_f}"
                                    )
                                    break
                            if _vs & no_vals.get(_f, set()):
                                bad = f"{_f}里已有被排除的取值，换一组再问"
                                break
                        if not bad and new_tokens:
                            for _h in history:
                                _hg, _ht = _cond_groups(str(_h.get("q", "")))
                                if _ht and str(_h.get("a", "")) == "是":
                                    bad = "已经确认过爱好，不要再问其他爱好"
                                    break
                        if bad:
                            rejected_dim = True
                            last_error = bad
                            logger.info(f"[BA20Q] 拒绝提问（{bad}）：{value}")
                            await asyncio.sleep(0.3)
                            continue
                    if kind == "ask" and force_guess:
                        rejected_force = True
                        last_error = f"已达到 {max_q} 问上限，必须给答案"
                        logger.info(f"[BA20Q] 超出上限，拒绝提问：{value}")
                        await asyncio.sleep(0.3)
                        continue
                    if kind == "ask" and any(n in value for n in LONG_NAMES):
                        rejected_name = True
                        last_error = "问题里不能出现学生名字"
                        logger.info(f"[BA20Q] 拒绝含名字的问题：{value}")
                        await asyncio.sleep(0.3)
                        continue
                    if kind == "ask" and any(
                        k in value for k in ("身高", "cm", "CM")
                    ):
                        rejected_height = True
                        last_error = "不能问身高（档案没有该数据）"
                        logger.info(f"[BA20Q] 拒绝身高问题：{value}")
                        await asyncio.sleep(0.3)
                        continue
                    if kind == "guess":
                        if value not in pool:
                            rejected_guess = True
                            last_error = f"「{value}」不在本局名单里"
                            logger.info(f"[BA20Q] 猜了名单外的角色：{value}")
                            await asyncio.sleep(0.3)
                            continue
                        if q_count < MIN_QUESTIONS:
                            rejected_guess = True
                            last_error = f"还没问满 {MIN_QUESTIONS} 问，先别猜"
                            logger.info(
                                f"[BA20Q] 拒绝过早猜测：仅 {q_count} 问"
                            )
                            await asyncio.sleep(0.3)
                            continue
                        _left = len(_candidates(history, excluded, pool))
                        if q_count < 10 and _left > 8:
                            rejected_guess = True
                            last_error = f"候选还有 {_left} 人，先别猜"
                            logger.info(
                                f"[BA20Q] 拒绝过早猜测：候选 {_left} 人，仅 {q_count} 问"
                            )
                            await asyncio.sleep(0.3)
                            continue
                        bad = _violations(value, history)
                        if bad:
                            rejected_guess = True
                            last_error = bad
                            logger.info(f"[BA20Q] 拒绝矛盾猜测：{value} — {bad}")
                            await asyncio.sleep(0.3)
                            continue
                    if kind == "ask":
                        sess["q_count"] = q_count + 1
                        q_count += 1
                    last_kind, last_value = kind, value
                    if kind == "guess" and len(history) < MIN_QUESTIONS:
                        last_error = "问题不足 6 个，禁止过早猜测"
                        logger.info(
                            f"[BA20Q] 拒绝过早猜测（仅 {len(history)} 问）：{value}"
                        )
                        await asyncio.sleep(0.3)
                        continue
                    return kind, value
                last_error = "模型没有给出有效问题"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    f"[BA20Q] 调用失败（第 {attempt + 1} 次）: {last_error}"
                )
                await asyncio.sleep(0.8)
        def _q_blocked(q: str) -> bool:
            yes_vals, no_vals = _answered_sets(history)
            groups, tokens = _cond_groups(q)
            for f, vs in groups.items():
                if f in yes_vals:
                    return True
                if vs & no_vals.get(f, set()):
                    return True
            if tokens:
                for h in history:
                    _, ht = _cond_groups(str(h.get("q", "")))
                    if ht and str(h.get("a", "")) == "是":
                        return True
            return False

        def safe_ask() -> str:
            if force_guess:
                return ""
            asked = {str(h.get("q", "")) for h in history}
            yes_vals, no_vals = _answered_sets(history)
            cands = _candidates(history, excluded, pool)
            from collections import Counter

            for field in ("weapon", "atk", "role", "pos", "year", "star", "club", "school"):
                if field in yes_vals:
                    continue
                counts = Counter(PROFILES[c].get(field, "") for c in cands)
                blocked = no_vals.get(field, set())
                for value, _ in counts.most_common():
                    if not value or value in ("—", "无") or value in blocked:
                        continue
                    q = _split_question(field, [value])
                    if q in asked or _q_blocked(q):
                        continue
                    sess["q_count"] = int(sess.get("q_count", 0) or 0) + 1
                    return q
            return ""

        if force_guess or rejected_force:
            cand = self._fallback_candidate(history, excluded, pool)
            if not cand:
                cand = next(
                    (n for n in pool if n not in (excluded or [])), ""
                )
            if cand:
                logger.info(f"[BA20Q] 问满强制作答：{cand}")
                return "guess", cand
        if rejected_dim or rejected_height or rejected_name or rejected_guess:
            q = safe_ask()
            if q:
                logger.info(f"[BA20Q] 改用安全提问：{q}")
                return "ask", q
            if _cands:
                logger.info(f"[BA20Q] 没有可问的问题，直接作答：{_cands[0]}")
                return "guess", _cands[0]
        if last_kind:
            if last_kind == "ask" and any(
                k in (last_value or "") for k in ("身高", "cm", "CM")
            ):
                q = safe_ask()
                if q:
                    return "ask", q
            return last_kind, last_value
        return "error", last_error

    @staticmethod
    def _parse_reply(text: str) -> tuple[str, str]:
        guess = re.search(r"GUESS[:：]\s*(.+)", text)
        ask = re.search(r"ASK[:：]\s*(.+)", text)
        if guess:
            name = guess.group(1).strip().splitlines()[0].strip(" 　\"'「」")
            if name in ALL_NAMES:
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

    @staticmethod
    def _mode_buttons() -> list:
        return [
            ActionRow(
                buttons=[
                    Button(
                        id="ba20q-mode-base",
                        label="🎯 只猜原版",
                        action=Button.CallbackAction(data="ba20q:mode:base"),
                        style=Button.Style.PRIMARY,
                    ),
                    Button(
                        id="ba20q-mode-costume",
                        label="🎭 含服装版",
                        action=Button.CallbackAction(data="ba20q:mode:costume"),
                        style=Button.Style.DEFAULT,
                    ),
                ]
            )
        ]

    async def _pick_mode(self, event: AstrMessageEvent) -> tuple[str, list | None]:
        """开局前让玩家选原版 / 含服装版。"""
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
        return "", (
            [
                Plain(
                    f"🎮 想猜哪种？\n\n"
                    f"· 只猜原版：{len(NAMES)} 位学生\n"
                    f"· 含服装版：{len(ALL_NAMES)} 位（泳装 / 礼服 / 新年 / 恐怖等）"
                )
            ]
            + self._mode_buttons()
        )

    async def _begin_game(
        self, event: AstrMessageEvent, mode: str = "base", with_image: bool = True
    ) -> tuple[str, list | None]:
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

        max_q = int(
            self.config.get("max_questions", MAX_QUESTIONS_DEFAULT)
            or MAX_QUESTIONS_DEFAULT
        )
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
            "q_count": 0,
            "max_q": max_q,
            "max_calls": max_q * 2,
            "mode": "base",
            "pool": list(NAMES),
            "platform": str(event.get_platform_name() or ""),
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
            return "", [
                [Plain(f"🤔 阿罗娜好像知道了……\n\n你心里想的是不是「{text}」？")]
                + self._buttons(sess_id, guessing=True)
            ]
        sess["question"] = text
        sess["state"] = "asking"
        self.sessions[gid] = sess
        self._save_sessions()
        card = [Plain(self._question_text(sess))] + self._buttons(sess_id, guessing=False)
        # 图片必须单独一条发送；带键盘（按钮）的消息不能同时带图片
        sent = False
        if with_image and ROSTER_PATH.is_file():
            try:
                await event.send(
                    MessageChain(
                        chain=[
                            Image.fromFileSystem(str(ROSTER_PATH)),
                            Plain("👆 原版角色一览，想好一位再来回答～"),
                        ]
                    )
                )
                sent = True
            except Exception as exc:
                logger.warning(f"[BA20Q] 本地角色图发送失败：{exc}")
        if sent:
            await asyncio.sleep(1.2)
        return "", [card]

    def _question_text(self, sess: dict) -> str:
        max_q = int(sess.get("max_q", MAX_QUESTIONS_DEFAULT) or MAX_QUESTIONS_DEFAULT)
        history = sess.get("history") or []
        q_no = max(1, min(int(sess.get("q_count", 0) or 0), max_q))
        lines = [
            f"🔮 BA 猜学生 · 第 {q_no}/{max_q} 问",
            "",
            f"❓ {sess.get('question', '')}",
        ]
        if not history:
            lines.append("")
            lines.append("（只猜原版学生，不含泳装/礼服等服装版）")
        plat = str(sess.get("platform") or "")
        if not plat.startswith("qq_official"):
            lines.append("（没有按钮就回复文字：是 / 不是 / 放弃）")
        if history:
            shown = history[-3:]
            lines.append("")
            lines.append("已答：" + " → ".join(h["a"] for h in shown))
            if len(history) > 3:
                lines[-1] += f"（共 {q_no} 问）"
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
    @filter.regex(r"(?i)^\s*(?:@\S+\s*)?[\s/]*ba猜学生(?:\s+(放弃|结束|重开|规则|统计))?$")
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
                "用「是 / 不是」回答阿罗娜的问题，"
                "她最多 12 问就会猜出你心里的碧蓝档案学生。\n"
                "⚠️ 只猜原版学生，不含泳装、礼服等服装版本。\n"
                "🖱 QQ 官方机器人：点按钮回答\n"
                "⌨️ NapCat 等平台：直接回复「是 / 不是 / 放弃」\n\n"
                "指令：\n"
                "  /ba猜学生       开始一局\n"
                "  /ba猜学生 放弃   结束当前这局\n"
                "  /ba猜学生 重开   重新开一局\n"
                "  /ba猜学生 统计   查看本群战绩\n\n"
                "每群同时只能有 1 局；超过 2 分钟没操作会自动算放弃。"
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

        err, batches = await self._begin_game(event)
        if batches is None:
            yield event.plain_result(err)
            return
        for i, batch in enumerate(batches):
            if i:
                await asyncio.sleep(1.0)
            yield event.chain_result(batch)

    @filter.regex(r"(?i)^\s*(是|不是|放弃|对|不对)\s*$")
    async def on_text_answer(self, event: AstrMessageEvent):
        """没有按钮的平台（如 NapCat）直接用文字回答。"""
        gid = self._group_key(event)
        sess = self.sessions.get(gid)
        if not sess:
            return
        uid = str(event.get_sender_id() or "")
        if sess.get("owner") != uid and not event.is_admin():
            return
        if time.time() - float(sess.get("ts", 0) or 0) > IDLE_TIMEOUT:
            return
        text = str(event.message_str or "").strip()
        if sess.get("state") == "guessing":
            action = {"对": "right", "是": "right",
                      "不对": "wrong", "不是": "wrong"}.get(text)
        else:
            action = {"是": "yes", "不是": "no"}.get(text)
        if text == "放弃":
            action = "giveup"
        if not action:
            return
        event.stop_event()
        sess["busy"] = True
        sess["ts"] = time.time()
        try:
            async for result in self._handle_action(
                event, sess, gid, sess.get("id"), action
            ):
                yield result
        finally:
            sess["busy"] = False
            sess["ts"] = time.time()
            if self.sessions.get(gid) is sess:
                self._save_sessions()

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
            # 再来一局：先清掉旧局，再重新发图 + 出题
            self.sessions.pop(self._group_key(event), None)
            self._save_sessions()
            err, batches = await self._begin_game(event, with_image=False)
            if batches is None:
                yield event.chain_result([Plain(err)] + self._end_buttons())
            else:
                for i, batch in enumerate(batches):
                    if i:
                        await asyncio.sleep(1.0)
                    yield event.chain_result(batch)
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
                [Plain("⏳ 超过 2 分钟没操作，这局先关掉啦（不计入统计）～ 想玩发 /ba猜学生。")]
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
                {
                    "q": sess.pop("canonical", None) or sess.get("question", ""),
                    "a": answer_map[action],
                }
            )
        else:
            return

        calls = int(sess.get("calls", 0) or 0)
        if action == "wrong" and int(sess.get("q_count", 0) or 0) >= int(
            sess.get("max_q", MAX_QUESTIONS_DEFAULT) or MAX_QUESTIONS_DEFAULT
        ):
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
