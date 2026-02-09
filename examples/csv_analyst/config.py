"""
Configuration for the CSV Analyst example agent.
"""

from sciagent.config import AgentConfig, SuggestionChip

CSV_CONFIG = AgentConfig(
    name="csv-analyst",
    display_name="CSV Analyst",
    description="A lightweight agent for exploring and analysing CSV data.",
    instructions="You are an expert data analyst. Help the user explore CSV files.",
    accepted_file_types=[".csv", ".tsv"],
    suggestion_chips=[
        SuggestionChip("Summarise this dataset", "Give me summary statistics."),
        SuggestionChip("Find outliers", "Detect outlier rows in the data."),
        SuggestionChip("Plot distributions", "Plot histograms of numeric columns."),
    ],
    logo_emoji="📊",
    accent_color="#2196F3",
    bounds={
        "row_count": {"min": 1, "max": 10_000_000, "unit": "rows"},
    },
    extra_libraries=["pandas", "seaborn"],
    output_dir="csv_output",
)
