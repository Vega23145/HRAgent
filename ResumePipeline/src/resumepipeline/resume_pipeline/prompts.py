SYSTEM_PROMPT = """Extract this resume into the schema. Use only facts in the text; never invent.
- Dates: YYYY-MM (YYYY if month unknown). Ongoing role: end="present".
- Fix PDF artefacts (split words like "T echnical", broken names).
- highlights: one short sentence each (max 20 words), keep numbers and metrics.
- skills: group by the resume's own headings; one item per skill.
- experience: internships and freelance work included. projects: tech = tools used.
- grade: as written (e.g. "8.00/10"). interests: hobbies/interests section only.
- Unknown scalar -> null. Missing section -> []."""
