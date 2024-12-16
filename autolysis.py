# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "seaborn",
#   "pandas",
#   "matplotlib",
#   "httpx",
#   "chardet",
#   "numpy",
#   "scipy"
# ]
# ///

import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import httpx
import chardet
from pathlib import Path
import asyncio
import numpy as np
from scipy.stats import ttest_ind

# API Configuration
API_ENDPOINT = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

# Function to fetch API token
def fetch_api_token():
    token = os.environ.get("AIPROXY_TOKEN")
    if not token:
        raise EnvironmentError("AIPROXY_TOKEN environment variable not found. Set it before running the script.")
    return token

async def read_csv_file(filepath):
    """Reads a CSV file and detects its encoding."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File '{filepath}' not found.")

    with open(filepath, 'rb') as file:
        detected_encoding = chardet.detect(file.read())['encoding']

    print(f"Detected file encoding: {detected_encoding}")
    return pd.read_csv(filepath, encoding=detected_encoding)

async def make_api_request(url, headers, payload):
    """Makes an asynchronous POST request."""
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

async def perform_analysis(dataframe, api_key):
    """Performs statistical analysis and communicates with an API for additional insights."""
    if dataframe.empty:
        raise ValueError("The dataset is empty.")

    numeric_data = dataframe.select_dtypes(include=[np.number])
    analysis_results = {
        'summary_statistics': dataframe.describe(include='all').to_dict(),
        'missing_data': dataframe.isnull().sum().to_dict(),
        'correlations': numeric_data.corr().to_dict() if not numeric_data.empty else {}
    }

    if 'Feature1' in dataframe.columns and 'Feature2' in dataframe.columns:
        t_stat, p_val = ttest_ind(dataframe['Feature1'].dropna(), dataframe['Feature2'].dropna())
        analysis_results['t_test'] = {'t_statistic': t_stat, 'p_value': p_val}

    payload = {
        "model": "gpt-4o-mini",
        "columns": dataframe.columns.tolist(),
        "data_preview": dataframe.head().to_dict(),
        "summary": analysis_results
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    api_response = await make_api_request(API_ENDPOINT, headers, payload)

    return analysis_results, api_response

async def create_visualizations(dataframe, output_directory):
    """Generates and saves plots from the data."""
    sns.set_theme(style="darkgrid")

    numeric_columns = dataframe.select_dtypes(include=[np.number]).columns
    output_directory.mkdir(parents=True, exist_ok=True)

    for column in numeric_columns[:3]:  # Limit to first 3 columns for simplicity
        plt.figure()
        sns.histplot(dataframe[column].dropna(), kde=True, color='blue')
        plt.title(f"Distribution of {column}")
        plt.savefig(output_directory / f"{column}_distribution.png")
        plt.close()

    if len(numeric_columns) > 1:
        plt.figure(figsize=(10, 8))
        corr_matrix = dataframe[numeric_columns].corr()
        sns.heatmap(corr_matrix, annot=True, cmap='viridis')
        plt.title("Correlation Heatmap")
        plt.savefig(output_directory / "correlation_heatmap.png")
        plt.close()

async def write_report(narrative, output_directory):
    """Writes a narrative report to a markdown file."""
    markdown_file = output_directory / "REPORT.md"
    with open(markdown_file, 'w') as file:
        file.write(narrative)
    print(f"Report saved at {markdown_file}")

async def process_file(filepath):
    """Main function to handle file processing, analysis, and visualization."""
    filepath = Path(filepath)
    output_dir = filepath.parent / f"{filepath.stem}_analysis"

    token = fetch_api_token()
    dataframe = await read_csv_file(filepath)

    analysis, narrative = await perform_analysis(dataframe, token)
    await create_visualizations(dataframe, output_dir)
    await write_report(narrative, output_dir)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    asyncio.run(process_file(input_file))
