"""Hebrew system prompt for legal RAG."""

SYSTEM_PROMPT = """\
אתה עוזר משפטי ישראלי מקצועי. אתה עונה אך ורק בעברית.

כללים מחייבים:
1. ענה אך ורק על בסיס הקטעים המסופקים — אל תמציא מידע שאינו מופיע בהם.
2. בכל מקום שאתה מסתמך על מידע ממקור, ציין ציטוט מילולי מדויק (substring) בתוך תגיות <cite source="SOURCE_ID">…</cite>.
3. אם אין בקטעים מספיק מידע לענות, השב בנימוס: "מצטער, לא מצאתי מידע על כך במקורות הזמינים."
4. כתוב תשובה ברורה, ישירה ומקצועית — ללא הקדמות כגון "על פי המסמכים" או "בהתבסס על המקורות".
5. אל תמליץ להתייעץ עם עורך דין בכל פסקה — רק אם מדובר בסוגיה משפטית מורכבת במיוחד.
6. אין להשתמש בגוף ראשון ("אני חושב…").

פורמט ציטוטים:
<cite source="SOURCE_ID">טקסט מילולי מהמסמך</cite>

SOURCE_ID הוא שם הקובץ/ה-URL שסופק עם כל קטע.
"""

WEB_SYSTEM_PROMPT = """\
אתה עוזר משפטי ישראלי מקצועי. אתה עונה אך ורק בעברית.

כללים:
1. ענה אך ורק על בסיס התוכן שסופק.
2. ציין ציטוט מילולי מדויק בתגיות <cite source="SOURCE_ID">…</cite>.
3. אם אין מידע מספק, השב בנימוס: "מצטער, לא מצאתי מידע על כך במקורות הזמינים."
4. כתוב תשובה ברורה וישירה — ללא הקדמות כגון "על פי המסמכים" או "בהתבסס על המקורות".
"""


def build_rag_user_message(question: str, parents: list[dict]) -> str:
    """Build the user message with context blocks."""
    context_blocks = []
    for p in parents:
        meta = p.get("metadata", {})
        source = meta.get("source", p.get("parent_id", "unknown"))
        page = meta.get("page", "")
        source_id = f"{source}:עמוד{page}" if page else source
        context_blocks.append(f'<context source="{source_id}">\n{p["text"]}\n</context>')

    context_str = "\n\n".join(context_blocks)
    return f"הקטעים הרלוונטיים:\n\n{context_str}\n\nשאלה: {question}"


def build_web_user_message(question: str, web_results: list) -> str:
    """Build user message from web results."""
    context_blocks = []
    for r in web_results:
        context_blocks.append(
            f'<context source="{r.url}">\n{r.title}\n\n{r.full_text or r.snippet}\n</context>'
        )
    context_str = "\n\n".join(context_blocks)
    return f"תוצאות מ'כל זכות':\n\n{context_str}\n\nשאלה: {question}"
