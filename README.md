# Temporal OpenAI LLM Streaming Workflow

This Python script demonstrates a Temporal workflow that streams responses from OpenAI's GPT model.

![CLI Run Animation](cli.gif)

## How it Works

1. The script starts a Temporal worker and executes a workflow.
2. The workflow runs an activity that streams responses from the GPT model.
3. The activity sends chunks of the response back to the workflow using signals (every 1 second).
4. The workflow accumulates these chunks and returns the final response.
5. A query can be made to the workflow to get the response as it is being built.

![Workflow UI](workflow-ui.png)

## Prerequisites

- Python 3.7+
- [Poetry](https://python-poetry.org/docs/#installation) (for dependency management)
- Temporal server running locally on port 7233
    - [brew install temporal](https://docs.temporal.io/cli/server#start-dev)
- [OpenAI API key](https://platform.openai.com/api-keys)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/steveandroulakis/temporal-openai-llm-streaming.git
   cd temporal-openai-llm-streaming
   ```

2. Install dependencies using Poetry:
   ```
   poetry install
   ```

3. Set your OpenAI API key as an environment variable:
   ```
   export OPENAI_API_KEY=your_api_key_here
   ```

## Usage

Run the script with a message as an argument. For example:

```
poetry run python workflow.py "Give me a couple of paragraphs about the history of the Roman Empire"
```

## Notes

- The script uses the GPT-4 model by default. You can change this in the `stream_gpt` function if needed.
- The OpenAI client is initialized inside the activity to comply with Temporal's sandbox restrictions.