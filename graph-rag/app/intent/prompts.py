"""Classification prompt — uses the REAL Bengaluru 40-PS field vocabulary
extracted from `bengaluru_40ps_1000_firs.json` (Phase 0 read).

The LLM output is ONLY ClassifiedIntent JSON. It never contains Cypher.
"""
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate


SYSTEM = """You are an intent classifier for a Karnataka State Police crime-records Graph-RAG system.
You receive an investigator's natural-language question and must emit a single JSON object
matching the schema below — no prose, no markdown, no commentary.

CRIME HEADS (case-insensitive, exact one-of): ROBBERY, BURGLARY, CYBER FRAUD, VEHICLE THEFT, EXTORTION.
CASE STATUS values: Pending Trial, Under Investigation, Dis/Acq.
CASE CATEGORY values: Heinous, Non Heinous.
DISTRICT in dataset: Bengaluru Urban.
POLICE STATIONS (40, suffix " PS"), e.g. Magadi Road PS, Electronic City PS, Indiranagar PS,
RT Nagar PS, Banashankari PS, Yeshwanthpur PS, Kothanur PS, Chandra Layout PS, Subramanyapura PS.
FIR ID format: exactly `<number>/<year>` (regex ^\\d+/\\d{4}$), e.g. 4/2023, 17/2023.
PHONE NUMBER format: international plus-prefixed digits (e.g. +919811223344).
VEHICLE PLATE format: KA-XX-XX-NNNN (e.g. KA-05-MB-1122).
GANG NAME examples: PhishNet Syndicate, Kala Nag Night Lockpicks.
AI METADATA fields: crime_pattern_id, linked_firs, confidence_score, is_repeat_offender, predicted_suspect.

INTENT TYPES — classify the user question into exactly one:
- find_fir_by_id: a specific FIR by its FIR id (e.g. "show me FIR 4/2023").
- find_firs_by_crime_type: list FIRs of a crime head (e.g. "all robbery cases").
- find_firs_by_location: FIRs in a district or police station.
- find_linked_firs: other FIRs linked to a given FIR (via ai_metadata.linked_firs).
- find_suspect_network: members of a gang / suspect associates for a named gang.
- find_by_digital_evidence: FIRs linked to a phone number or vehicle plate.
- semantic_search: free-form natural-language question with no concrete entity above
  (e.g. "what became of the Indiranagar cyber-fraud ring?").
- unsupported: cannot map to any of the above.

Fill ONLY the entity fields relevant to the chosen intent; leave others as null.
free_text is ONLY populated (non-null) for semantic_search.
confidence is your self-assessed 0.0–1.0 confidence in the chosen intent.

OUTPUT JSON SCHEMA (return EXACTLY this shape, no surrounding text):
{{
  "intent": "<one of the intent values above>",
  "entities": {{
    "fir_id": "<string or null>",
    "crime_head": "<string or null>",
    "district": "<string or null>",
    "police_station": "<string or null>",
    "phone_number": "<string or null>",
    "vehicle_number": "<string or null>",
    "gang_name": "<string or null>",
    "date_from": "<YYYY-MM-DD or null>",
    "date_to": "<YYYY-MM-DD or null>",
    "free_text": "<string or null>"
  }},
  "confidence": 0.0
}}
"""


HUMAN = "Classify this question: {query}"


def build_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM),
        HumanMessagePromptTemplate.from_template(HUMAN),
    ])
