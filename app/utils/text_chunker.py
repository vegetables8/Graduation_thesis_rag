def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """
    将长文本切分为带重叠的语义片段。

    重叠区的意义在于：
    前后文不会被硬切断，检索时可以提高答案的连贯度。
    """

    normalized = (text or "").strip()
    if not normalized:
        return []

    paragraphs = [item.strip() for item in normalized.splitlines() if item.strip()]
    if not paragraphs:
        return [normalized]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        # 如果当前片段叠加新段落后仍不超过上限，则继续合并，
        # 这样可以尽量保留自然段语义结构。
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        # 超长段落再进行二次切分。
        if len(paragraph) > chunk_size:
            start = 0
            while start < len(paragraph):
                end = start + chunk_size
                chunks.append(paragraph[start:end])
                start = max(end - overlap, start + 1)  # 关键，确保不重叠
            current = ""
        else:
            current = paragraph

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk.strip()]
