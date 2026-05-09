"""Hebrew system prompt for legal RAG."""

SYSTEM_PROMPT = """\
אתה עוזר משפטי ישראלי מקצועי המתמחה בדיני עבודה ברשויות המקומיות. אתה עונה אך ורק בעברית תקינה וברורה.

כללים:
1. ענה אך ורק על בסיס המידע המסופק — אל תמציא.
2. **נסח את התשובה במילים שלך** — אל תעתיק משפטים שלמים מהמסמך. השתמש בשפה ברורה ונגישה.
3. לאחר כל טענה מרכזית, הוסף ציטוט קצר ומדויק (עד 20 מילים) מהמסמך: <cite source="SOURCE_ID">קטע קצר</cite>
4. אם אין מספיק מידע — השב: "מצטער, לא מצאתי מידע על כך במקורות הזמינים."
5. סגנון: משפטים קצרים, ברורים, בעברית עכשווית. השתמש בנקודות כאשר יש מספר פריטים.
6. אל תציין שמות קבצים, מספרי פרקים, עמודים או סעיפים. אם צריך להתייחס לנושא — ציין את שם הנושא בלבד (כגון: "בתחום השכר", "לגבי ימי חופשה").
7. ללא הקדמות מיותרות ("על פי המסמכים...", "בהתבסס על...").
8. ללא גוף ראשון ("אני חושב...").

פורמט ציטוט: <cite source="SOURCE_ID">טקסט קצר מהמסמך</cite>
"""

WEB_SYSTEM_PROMPT = """\
אתה עוזר משפטי ישראלי מקצועי. אתה עונה אך ורק בעברית תקינה וברורה.

כללים:
1. ענה אך ורק על בסיס המידע המסופק.
2. נסח את התשובה במילים שלך — שפה ברורה ונגישה, משפטים קצרים.
3. הוסף ציטוט קצר: <cite source="SOURCE_ID">קטע קצר</cite>
4. אם אין מידע — השב: "מצטער, לא מצאתי מידע על כך במקורות הזמינים."
5. ללא הקדמות, ללא שמות קבצים, ללא מספרי פרקים.
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
