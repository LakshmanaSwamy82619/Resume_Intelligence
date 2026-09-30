"""
A curated skills/technology taxonomy for rule-based extraction.

This is used only for STRUCTURING (turning resume text into a structured,
evidence-linked candidate record) -- it is explicitly NOT used as the sole
retrieval/matching mechanism (Section 9 forbids keyword-only matching for
that). Retrieval and ranking use hybrid semantic+lexical retrieval and LLM
agents on top of this structured data; this taxonomy just gives the
structuring step a grounded vocabulary so extracted "skills" are real,
canonical technology/skill names rather than arbitrary noun phrases.

Not exhaustive by design -- it is intentionally a living list (Section 42:
avoid hard-coded configuration bloat). New terms can be appended without
touching extraction logic.
"""
from __future__ import annotations

TECHNICAL_SKILLS: list[str] = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "c", "go", "golang", "rust", "ruby", "php",
    "kotlin", "swift", "scala", "r", "matlab", "sql", "bash", "shell scripting", "perl",
    # Web / backend frameworks
    "django", "flask", "fastapi", "spring", "spring boot", "express", "express.js", "node.js", "nestjs",
    "asp.net", ".net", "rails", "laravel", "graphql", "rest api", "grpc",
    # Frontend
    "react", "react.js", "angular", "vue", "vue.js", "redux", "next.js", "html", "css", "sass", "tailwind css",
    "bootstrap", "jquery", "webpack",
    # Data / ML / AI
    "machine learning", "deep learning", "nlp", "natural language processing", "computer vision",
    "scikit-learn", "tensorflow", "pytorch", "keras", "xgboost", "lightgbm", "pandas", "numpy",
    "data analysis", "data science", "data engineering", "data visualization", "tableau", "power bi",
    "statistics", "a/b testing", "feature engineering", "llm", "large language models", "langchain",
    "langgraph", "generative ai", "transformers", "hugging face", "opencv", "reinforcement learning",
    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch", "sqlite", "oracle",
    "cassandra", "dynamodb", "pgvector", "vector database", "snowflake", "bigquery", "redshift",
    # Cloud / DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform", "ansible", "jenkins",
    "ci/cd", "github actions", "gitlab ci", "cloudformation", "helm", "prometheus", "grafana",
    "microservices", "serverless", "lambda",
    # Messaging / streaming
    "kafka", "rabbitmq", "celery", "airflow", "spark", "hadoop", "flink",
    # Tools / practices
    "git", "linux", "agile", "scrum", "jira", "unit testing", "tdd", "system design",
    "object-oriented programming", "oop", "design patterns", "api design", "load balancing",
    # Mobile
    "android", "ios", "react native", "flutter",
]

SOFT_SKILLS: list[str] = [
    "communication", "leadership", "teamwork", "collaboration", "problem solving", "problem-solving",
    "critical thinking", "time management", "adaptability", "creativity", "attention to detail",
    "stakeholder management", "mentoring", "conflict resolution", "presentation skills",
    "project management", "decision making", "analytical thinking", "ownership",
]

CERTIFICATION_KEYWORDS: list[str] = [
    "aws certified", "azure certified", "google cloud certified", "pmp", "scrum master", "csm",
    "cka", "ckad", "comptia", "ccna", "cissp", "six sigma", "itil", "oracle certified",
    "certified kubernetes", "tensorflow developer certificate", "deep learning specialization",
]

DEGREE_KEYWORDS: list[str] = [
    "b.tech", "btech", "b.e.", "bachelor of technology", "bachelor of engineering",
    "m.tech", "mtech", "master of technology", "b.sc", "bsc", "m.sc", "msc",
    "bachelor of science", "master of science", "mba", "master of business administration",
    "b.com", "m.com", "bca", "mca", "phd", "ph.d", "diploma", "b.a.", "m.a.",
    "bachelor of arts", "master of arts", "associate degree",
]
