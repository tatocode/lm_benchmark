from llm_benchmark.bench.workload import (
    DEFAULT_IMAGE_ID,
    IGNORE_PREFIX,
    SAMPLE_QUESTIONS,
    VISION_QUESTIONS,
    build_prompt,
    compose_prompt,
    count_tokens,
    get_builtin_image,
    list_builtin_images,
    load_sample_image_b64,
)


def test_count_tokens_positive():
    assert count_tokens("hello world") > 0
    assert count_tokens("大模型推理性能测试") > 0


def test_build_prompt_hits_target():
    for target in (64, 256, 1024):
        prompt = build_prompt(target, variant=0)
        got = count_tokens(prompt)
        assert abs(got - target) <= target * 0.15 + 8, (target, got)


def test_build_prompt_variants_differ():
    a = build_prompt(512, variant=0)
    b = build_prompt(512, variant=1)
    assert a != b


def test_build_prompt_small_target():
    prompt = build_prompt(8, variant=0)
    assert len(prompt) > 0
    assert prompt in SAMPLE_QUESTIONS


def test_build_prompt_decoy_then_question():
    prompt = build_prompt(512, variant=0)
    assert prompt.startswith(IGNORE_PREFIX)
    assert any(prompt.endswith(q) for q in SAMPLE_QUESTIONS)


def test_vision_prompt():
    prompt = build_prompt(256, variant=0, with_image=True)
    assert count_tokens(prompt) > 0
    assert any(prompt.endswith(q) for q in VISION_QUESTIONS)


def test_compose_prompt_custom_question():
    q = "自定义问题：请解释压测中的 P95 是什么意思。"
    prompt = compose_prompt(256, q, variant=3)
    assert prompt.endswith(q)
    assert prompt.startswith(IGNORE_PREFIX)
    assert abs(count_tokens(prompt) - 256) <= 256 * 0.15 + 8


def test_builtin_images_available():
    images = list_builtin_images()
    assert len(images) >= 4
    for meta in images:
        assert meta["source"] == "builtin"
        got = get_builtin_image(meta["id"])
        assert got is not None
        data, mime = got
        assert len(data) > 1000
        assert mime.startswith("image/")


def test_load_sample_image_default():
    b64 = load_sample_image_b64()
    assert len(b64) > 1000
    # JPEG 的 base64 以 "/9j/" 开头
    assert b64.startswith("/9j/")
    assert DEFAULT_IMAGE_ID.startswith("builtin:")
