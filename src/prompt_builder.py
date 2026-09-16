"""Builds structured prompts for reliable SQL generation."""


def build_prompt(question: str, context_chunks: list, previous_error: str = None) -> str:
    schema_parts = []
    definition_parts = []
    example_parts = []

    for chunk in context_chunks:
        kind = chunk["metadata"]["type"]

        if kind == "schema":
            schema_parts.append(chunk["text"])

        elif kind == "definition":
            definition_parts.append(chunk["text"])

        elif kind == "example":
            example_parts.append(chunk["text"])

    sections = []

    if schema_parts:
        sections.append(
            "### Relevant database schema\n"
            + "\n\n".join(schema_parts)
        )

    if definition_parts:
        sections.append(
            "### Relevant business definitions\n"
            + "\n\n".join(definition_parts)
        )

    if example_parts:
        sections.append(
            "### Relevant examples\n"
            + "\n\n".join(example_parts)
        )

    sections.append(
        """### SQL generation requirements

Determine the requested result shape from the question.

Examples:

- "How many employees are currently active?"
  -> one aggregate result.

- "How many employees are currently working in each department?"
  -> one row for every department.
  -> GROUP BY department.
  -> DO NOT use LIMIT 1.

- "Which department currently has the highest headcount?"
  -> one department.
  -> GROUP BY department.
  -> ORDER BY count DESC.
  -> LIMIT 1 is appropriate.

- "Show employee count by department."
  -> one row for every department.
  -> GROUP BY department.

- "Show the top 5 highest paid employees."
  -> ORDER BY salary DESC.
  -> LIMIT 5.

Do not answer a different but related question.
"""
    )

    sections.append(f"### User question\n{question}")

    if previous_error:
        sections.append(
            "### Validation feedback from the previous attempt\n"
            f"{previous_error}\n\n"
            "Generate a corrected query. The previous query must not be repeated."
        )

    sections.append(
        "### Final output requirement\n"
        "Return ONLY the PostgreSQL SELECT statement. "
        "Do not include markdown, explanation, or comments."
    )

    return "\n\n".join(sections)