"""Example systems for the form. Together they cover the classes prohibited, high, limited, minimal and
unclear, a general-purpose AI model and a description in Dutch."""

from __future__ import annotations

from app.schemas import Example

EXAMPLES: list[Example] = [
    Example(
        id="cv-screening",
        title="CV screening tool",
        role="provider",
        expected="high",
        description=(
            "We are a software company in Ghent and sell a cloud tool to HR departments across the EU. "
            "The tool reads incoming CVs and cover letters, extracts skills and experience with a language model, "
            "and ranks every applicant against the job ad with a score from 0 to 100. "
            "Recruiters see the ranked list and usually only open the top 20 applications. "
            "Applicants below a score of 40 get an automatic rejection mail."
        ),
    ),
    Example(
        id="call-center-emotion",
        title="Emotion tracking of call center staff",
        role="deployer",
        expected="prohibited",
        description=(
            "Our call center in Lisbon wants to buy a system that listens to the voice of our employees during calls. "
            "It infers from tone, pitch and speech rate whether the agent is stressed, bored or angry. "
            "Team leaders get a weekly dashboard with an emotion score per employee, "
            "and the score is one input in the yearly performance review. "
            "The purpose is to improve the quality of our service, not health or safety."
        ),
    ),
    Example(
        id="radiology-triage",
        title="Lung nodule detection in CT scans",
        role="provider",
        expected="high",
        description=(
            "We develop software that analyzes chest CT scans and marks suspected lung nodules for the radiologist, "
            "with an estimate of how likely each nodule is malignant. "
            "The software is a medical device under Regulation (EU) 2017/745 in risk class IIb, "
            "so a notified body assesses its conformity before we can place it on the market. "
            "Hospitals in Germany and the Netherlands will use it in their daily reading workflow."
        ),
    ),
    Example(
        id="webshop-chatbot",
        title="Customer service chatbot",
        role="provider",
        expected="limited",
        description=(
            "We run a webshop for garden furniture and built a chat assistant on our website. "
            "It answers questions about products, delivery times and returns in natural language, "
            "using a large language model from an external provider through its API and our own product catalog. "
            "It cannot place orders, give refunds or make any decision about a customer; "
            "difficult questions are handed over to a human colleague."
        ),
    ),
    Example(
        id="demand-forecast",
        title="Stock demand forecasting",
        role="deployer",
        expected="minimal",
        description=(
            "Our supermarket chain uses a machine learning model that predicts how many units of each product "
            "every store will sell next week. "
            "It learns from past sales, weather data, holidays and promotions. "
            "Store managers use the forecast to place orders with suppliers. "
            "The system uses no data about individual customers or employees."
        ),
    ),
    Example(
        id="open-weight-llm",
        title="Open-weight language model",
        role="provider",
        # The paid API is a general-purpose AI system generating text, so Article 50(2) applies;
        # gpai.applies is true for the model (eval case gpai-open-weights-llm).
        expected="limited",
        description=(
            "Our lab in Paris pre-trains a 12 billion parameter language model on a large web and code corpus. "
            "The model writes text, answers questions, translates, summarizes and writes code in many languages. "
            "We publish the weights under an open license on a public model hub and also sell access through our own API. "
            "Other companies build their own products on top of it. "
            "The training compute was about 3 x 10^23 floating point operations."
        ),
    ),
    Example(
        id="hr-helper-unclear",
        title="HR assistant (vague)",
        role="unknown",
        expected="unclear",
        description=(
            "We want to use an AI tool that helps our HR team work with employee data. "
            "It looks at information from our HR system and gives suggestions to the team. "
            "The team can decide what to do with the suggestions. "
            "We have not decided yet which data it will use."
        ),
    ),
    Example(
        id="credit-scoring-nl",
        title="Kredietscore voor consumenten (Dutch)",
        role="provider",
        expected="high",
        description=(
            "Wij zijn een Belgische fintech en bouwen een model dat de kredietwaardigheid van particulieren inschat. "
            "Het model gebruikt inkomen, uitgavenpatronen uit bankgegevens en betalingsgeschiedenis "
            "en geeft elke aanvrager een score. "
            "Banken die onze dienst afnemen, gebruiken de score om een consumentenkrediet toe te kennen of te weigeren. "
            "Fraudedetectie is niet het doel van het systeem."
        ),
    ),
]


def list_examples() -> list[dict]:
    return [e.model_dump() for e in EXAMPLES]
