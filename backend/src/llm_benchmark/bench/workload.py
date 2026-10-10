import base64
import math
import threading
from functools import lru_cache
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
VISION_DIR = ASSET_DIR / "vision"

# 内置视觉测试图片：均为来自 Wikimedia Commons 的真实照片 / 图像，
# 许可为公有领域或知识共享（保留署名信息，见 credit/title/license）。
BUILTIN_IMAGES = [
    {
        "id": "builtin:golden-gate",
        "name": "金门大桥 · 风景",
        "file": "golden-gate.jpg",
        "mime": "image/jpeg",
        "title": "GoldenGateBridge-001.jpg",
        "license": "CC BY 2.5",
        "credit": "Wikimedia Commons",
    },
    {
        "id": "builtin:food",
        "name": "健康食物 · 静物",
        "file": "food.jpg",
        "mime": "image/jpeg",
        "title": "Good Food Display - NCI Visuals Online.jpg",
        "license": "Public domain",
        "credit": "National Cancer Institute",
    },
    {
        "id": "builtin:great-wall",
        "name": "长城 · 地标",
        "file": "great-wall.jpg",
        "mime": "image/jpeg",
        "title": "Great Wall of China July 2006.JPG",
        "license": "CC0",
        "credit": "Wikimedia Commons",
    },
    {
        "id": "builtin:pillars",
        "name": "创生之柱 · 天文",
        "file": "pillars.jpg",
        "mime": "image/jpeg",
        "title": "Pillars of creation 2014 HST WFC3-UVIS full-res denoised.jpg",
        "license": "Public domain",
        "credit": "NASA / ESA / Hubble",
    },
    {
        "id": "builtin:mona-lisa",
        "name": "蒙娜丽莎 · 名画",
        "file": "mona-lisa.jpg",
        "mime": "image/jpeg",
        "title": "Mona Lisa, by Leonardo da Vinci, from C2RMF retouched.jpg",
        "license": "Public domain",
        "credit": "Leonardo da Vinci",
    },
    {
        "id": "builtin:apple",
        "name": "红苹果 · 物体",
        "file": "apple.jpg",
        "mime": "image/jpeg",
        "title": "Red Apple.jpg",
        "license": "CC BY 2.0",
        "credit": "Wikimedia Commons",
    },
    {
        "id": "builtin:apollo11",
        "name": "阿波罗 11 号 · 历史",
        "file": "apollo11.jpg",
        "mime": "image/jpeg",
        "title": "Apollo 11 first step.jpg",
        "license": "Public domain",
        "credit": "NASA",
    },
    {
        "id": "builtin:earth",
        "name": "蓝色弹珠 · 地球",
        "file": "earth.jpg",
        "mime": "image/jpeg",
        "title": "The Earth seen from Apollo 17.jpg",
        "license": "Public domain",
        "credit": "NASA / Apollo 17",
    },
]

DEFAULT_IMAGE_ID = BUILTIN_IMAGES[0]["id"]

SAMPLE_QUESTIONS = [
    "请用三句话解释什么是向量数据库，并说明它在检索增强生成中的作用。",
    "Explain the difference between latency and throughput in the context of serving large language models.",
    "写一首关于春天的四行短诗，要求包含“风”和“光”两个字。",
    "What are the trade-offs between speculative decoding and standard autoregressive decoding?",
    "总结大模型推理优化的三种常见手段，并分别说明其适用场景。",
    "Describe how attention mechanisms scale with sequence length and what optimizations exist.",
    "请把下面这句话翻译成英文：高性能推理服务需要在延迟、吞吐和成本之间取得平衡。",
    "List five practical tips for writing clear and testable software requirements.",
]

VISION_QUESTIONS = [
    "请详细描述这张图片中的内容，包括主要物体、颜色和布局。",
    "Describe this image in detail: what are the main objects, colors and layout?",
    "这张图片里有哪些几何元素？请按颜色和位置分别说明。",
    "What can you infer about this image? Give a concise summary in English.",
]

# 与问题无关的“干扰语料”，用于把输入长度凑到目标 token 数。
# 覆盖人工智能、系统、数据库、软件工程、金融、医疗、自然科学、历史、心理、
# 能源与环境等多个领域，中英混合，尽量贴近真实文档，避免明显重复。
_FILLER_PARAGRAPHS = [
    "大型语言模型通过在海量文本上预训练来学习语言的统计规律，再经过指令微调与人类反馈对齐，从而具备对话与推理能力。推理阶段的核心瓶颈通常在于显存带宽与 KV Cache 的读写，而非单纯的算力。",
    "Transformer 架构依赖自注意力机制在序列内部建立全局依赖，其计算复杂度随序列长度呈二次增长。为此业界提出了稀疏注意力、滑窗注意力与线性注意力等改进方案，以降低长上下文的成本。",
    "A retrieval-augmented generation pipeline first encodes the query, retrieves the most relevant document chunks from a vector store, and then conditions the language model on both the query and the retrieved context. This grounding step significantly reduces hallucination on knowledge-intensive tasks.",
    "向量索引常见的有 HNSW、IVF-PQ 与 DiskANN 等，它们在召回率、内存占用与查询延迟之间做出不同权衡。选择合适的索引往往比盲目增大模型更能改善端到端的检索体验。",
    "现代推理服务普遍采用连续批处理（continuous batching）来提升 GPU 利用率：新的请求可以在任意解码步加入正在运行的批次，而无需等待整批完成。配合 PagedAttention 对 KV Cache 的分页管理，显存碎片可显著减少。",
    "量化技术将模型权重从 FP16 压缩到 INT8 或 INT4，在几乎不损失精度的前提下大幅降低显存占用与带宽需求。主流量化方法包括 GPTQ、AWQ 以及训练后量化的 SmoothQuant 等。",
    "Distributed training splits the workload across many accelerators using data parallelism, tensor parallelism, and pipeline parallelism. Communication overhead, not raw compute, often becomes the limiting factor as the cluster grows.",
    "在网络层面，RDMA 与 InfiniBand 能够绕过内核协议栈，把跨节点的通信延迟降到微秒级。这对于张量并行中频繁的 all-reduce 操作尤为关键。",
    "关系型数据库通过 B+ 树索引在磁盘上实现高效的范围查询，而 LSM-Tree 则更适合写多读少的场景，它把随机写转换为顺序写以提升吞吐。两者在事务与压缩策略上各有取舍。",
    "分布式共识算法如 Raft 与 Paxos 通过选举与日志复制保证多个副本之间的一致性。在实际系统中，网络分区与时钟漂移是必须谨慎处理的两个难题。",
    "缓存系统通常采用 LRU、LFU 或 ARC 等淘汰策略来在有限内存中保留最有价值的数据。命中率的微小提升往往能带来后端负载的显著下降。",
    "消息队列通过解耦生产者与消费者来平滑流量峰值，Kafka 借助分区与顺序写盘实现高吞吐，而 RocketMQ 在事务消息方面提供了更完善的支持。",
    "良好的软件需求应当是可验证、无歧义且独立于具体实现的。用具体的验收标准描述期望行为，能够显著减少开发与测试之间的来回沟通成本。",
    "单元测试应聚焦于单一职责、运行快速且彼此隔离，而集成测试则用于验证组件之间的协作。二者结合才能在重构时提供足够的信心。",
    "代码评审的目的不是挑错，而是共享上下文并尽早发现设计层面的问题。把评审意见限定在可操作的范围内，可以避免不必要的争论。",
    "Refactoring is the disciplined process of improving the internal structure of code without changing its observable behavior. Small, incremental steps backed by a solid test suite make it safe.",
    "持续集成要求每次提交都自动触发构建与测试，从而尽早暴露集成缺陷。流水线的速度直接影响开发者的反馈循环。",
    "在资产配置中，分散化通过组合相关性较低的资产来降低整体波动，但系统性风险无法被完全消除。夏普比率衡量的是每单位风险所获得的超额收益。",
    "复利的力量来自时间：即使年化收益率不高，只要持续足够长，本金的增长也会呈现指数形态。这也解释了为什么尽早开始储蓄如此重要。",
    "Central banks influence economic activity through interest rates and open market operations. The transmission mechanism, however, operates with lags that are both variable and hard to measure.",
    "风险管理强调识别、度量与控制三个环节，其中风险的价值在于被定价而非被回避。过度集中是许多投资失败案例的共同特征。",
    "循证医学要求临床决策建立在最佳研究证据、医生经验与患者价值取向三者的结合之上。随机对照试验被视为评价疗效的金标准。",
    "睡眠对认知功能与免疫调节至关重要，长期睡眠不足会提高代谢与心血管疾病的风险。保持规律的作息往往比单纯延长睡眠时间更有效。",
    "Vaccines work by training the immune system to recognize a pathogen without causing the disease itself. Herd immunity protects those who cannot be vaccinated, provided coverage remains sufficiently high.",
    "热力学第二定律指出，孤立系统的熵不会自发减少，这为能量转换的效率设定了根本上限。永动机之所以不可能，正源于此。",
    "光的波粒二象性表明，微观粒子既表现出波动性也表现出粒子性，具体呈现哪一种取决于观测方式。量子力学用概率幅来描述这种不确定性。",
    "地球气候系统受到温室气体浓度的强烈影响，二氧化碳的辐射强迫会放大水汽反馈，从而形成正反馈循环。气候模型通过耦合大气、海洋与陆面过程来估计未来升温幅度。",
    "Evolution by natural selection requires variation, heritability, and differential reproductive success. Over long timescales, these simple ingredients produce remarkable biological diversity.",
    "丝绸之路不仅是一条贸易通道，更是技术、宗教与艺术跨文明传播的纽带。沿线城市的兴衰往往与商路的改道密切相关。",
    "印刷术的普及大幅降低了知识传播的成本，推动了宗教改革与科学革命。信息传播方式的变革常常先于社会结构的深刻调整。",
    "The invention of the steam engine marked the transition from agrarian economies to industrial ones. It also triggered profound changes in labor, urbanization, and living standards.",
    "认知偏差是人类在信息处理中系统性地偏离理性的模式，例如确认偏误使人倾向于搜寻支持既有观点的证据。了解这些偏差有助于做出更审慎的决策。",
    "刻意练习强调在舒适区之外、有明确反馈并高度专注的重复训练，它是专业技能提升的关键因素之一，而非单纯的时间投入。",
    "Emotional regulation involves recognizing, understanding, and modulating one's affective states. Simple techniques such as reframing and mindful breathing can reduce acute stress responses.",
    "光伏发电的成本在过去十年中大幅下降，使其在许多地区成为最便宜的电力来源之一。储能与电网灵活性成为进一步普及的关键约束。",
    "风力涡轮机通过空气动力学升力驱动叶片旋转，将动能转化为电能。选址时需综合考虑风资源、并网条件与生态影响。",
    "Nuclear fission releases energy by splitting heavy nuclei, producing no direct carbon emissions. Managing long-lived radioactive waste remains the central long-term challenge.",
    "规模经济使得产量增加时单位成本下降，但过度扩张也可能带来管理效率的下降，即所谓的规模不经济。企业需要在两者之间寻找平衡点。",
    "供应链的韧性来自冗余、多样化与可见性。全球化在提升效率的同时，也把局部冲击通过复杂的依赖网络传导到更广的范围。",
    "Statistics helps us distinguish signal from noise by quantifying uncertainty. A confidence interval communicates a range of plausible values, which is often more honest than a single point estimate.",
    "项目管理中的关键路径决定了整体的最短工期，任何位于关键路径上的延迟都会直接推迟交付。资源应向关键活动倾斜。",
    "Open source communities succeed when contribution is low-friction and governance is transparent. Clear documentation and friendly onboarding often matter more than raw technical merit.",
]

# 干扰块的前缀与真问题的引导语：把无关文本放在前面并要求忽略，问题放在最后，
# 既凑足了输入长度，又尽量不干扰模型对真实问题的理解。
IGNORE_PREFIX = "这是一段无用文本，请忽略："
ANSWER_LEAD = "现在请你回答："

_enc_lock = threading.Lock()
_encoding = None
_encoding_failed = False


def _get_encoding():
    global _encoding, _encoding_failed
    if _encoding_failed:
        return None
    if _encoding is None:
        with _enc_lock:
            if _encoding is None:
                try:
                    import tiktoken

                    _encoding = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    _encoding_failed = True
                    return None
    return _encoding


def count_tokens(text: str) -> int:
    enc = _get_encoding()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    return _estimate_tokens(text)


def _estimate_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    other = len(text) - cjk
    return max(1, math.ceil(other / 4) + math.ceil(cjk / 1.5))


def _truncate_to_tokens(text: str, target: int) -> str:
    enc = _get_encoding()
    if enc is not None:
        try:
            return enc.decode(enc.encode(text)[:target])
        except Exception:
            pass
    if target <= 0:
        return ""
    return text[: int(target * 4)]


@lru_cache(maxsize=512)
def compose_prompt(target_tokens: int, question: str, variant: int = 0) -> str:
    """用指定问题构造长度为 ``target_tokens`` 的提示词。

    结构为：无用的干扰文本在前（凑 token），真实问题在最后。问题置于末尾，
    符合模型对结尾内容更敏感的特性，同时干扰块被明确要求忽略，尽量减少对
    真实问题语义的干扰。
    """
    head = f"{IGNORE_PREFIX}\n"
    tail = f"\n\n{ANSWER_LEAD}{question}"
    need = target_tokens - count_tokens(head + tail)
    if need <= 0:
        # 目标长度太小，装不下干扰块，直接只给问题。
        return question

    offset = (variant * 5) % len(_FILLER_PARAGRAPHS)
    rotated = _FILLER_PARAGRAPHS[offset:] + _FILLER_PARAGRAPHS[:offset]
    body = ""
    total = 0
    i = 0
    while total < need and i < 100000:
        body += rotated[i % len(rotated)] + " "
        total = count_tokens(body)
        i += 1
    if total > need:
        body = _truncate_to_tokens(body, need)

    return (head + body.rstrip() + tail).strip()


def build_prompt(target_tokens: int, variant: int, with_image: bool = False) -> str:
    """按默认题库构造提示词（保持向后兼容，便于测试与默认场景）。"""
    pool = VISION_QUESTIONS if with_image else SAMPLE_QUESTIONS
    return compose_prompt(target_tokens, pool[variant % len(pool)], variant)


def list_builtin_images() -> list[dict]:
    return [
        {
            "id": m["id"],
            "name": m["name"],
            "source": "builtin",
            "mime": m["mime"],
            "url": f"/api/images/{m['id']}/raw",
            "credit": f"{m['credit']} · {m['license']}",
            "size": 0,
        }
        for m in BUILTIN_IMAGES
    ]


def get_builtin_image(image_id: str) -> tuple[bytes, str] | None:
    for m in BUILTIN_IMAGES:
        if m["id"] == image_id:
            path = VISION_DIR / m["file"]
            if path.exists():
                return path.read_bytes(), m["mime"]
    return None


def load_sample_image_b64(image_id: str = "") -> str:
    got = get_builtin_image(image_id or DEFAULT_IMAGE_ID)
    if got is None:
        got = get_builtin_image(DEFAULT_IMAGE_ID)
    data, _ = got  # type: ignore[misc]
    return base64.b64encode(data).decode()
