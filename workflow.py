#!/usr/bin/env python3
"""
LLM Stream Workflow

This script runs a Temporal workflow that streams responses from OpenAI's GPT model.

Example: poetry run python workflow.py "Give me a couple of paragraphs on the history of the Roman Empire."
"""

import asyncio
import os
import time
import argparse
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

# Constants
TEMPORAL_SERVER = "localhost:7233"
TASK_QUEUE = "llm-stream-task-queue"
WORKFLOW_ID = "llm-stream-workflow"
TIME_WINDOW = 1  # seconds


@activity.defn
async def stream_gpt(message: str) -> str:
    """Stream responses from GPT model."""
    # Import OpenAI client inside the activity to avoid sandbox restrictions
    from openai import AsyncOpenAI

    openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    client = await Client.connect(TEMPORAL_SERVER)
    wf = client.get_workflow_handle(activity.info().workflow_id)

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": message}],
        temperature=0,
        stream=True,
    )

    accumulated_content = ""
    start_time = time.time()
    async for chunk in response:
        activity.heartbeat()
        chunk_content = (
            chunk.choices[0].delta.content
            if chunk.choices and chunk.choices[0].delta.content
            else ""
        )
        accumulated_content += chunk_content
        current_time = time.time()
        if current_time - start_time >= TIME_WINDOW:
            await wf.signal("update_response", accumulated_content)
            accumulated_content = ""
            start_time = current_time

    if accumulated_content:
        await wf.signal("update_response", accumulated_content)

    return "Streaming completed"


@workflow.defn
class LLMStreamWorkflow:
    """Workflow for streaming LLM responses."""

    def __init__(self):
        self.response = ""

    @workflow.signal
    def update_response(self, chunk: str):
        """Update the response with a new chunk."""
        self.response += chunk

    @workflow.query
    def get_response(self) -> str:
        """Get the current accumulated response."""
        return self.response

    @workflow.run
    async def run(self, message: str) -> str:
        """Run the workflow."""
        await workflow.execute_activity(
            stream_gpt,
            message,
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=10),
        )
        return f"{self.response}"


async def run_workflow(message: str):
    """Run the LLM stream workflow with continuous querying and streaming terminal output."""
    client = await Client.connect(TEMPORAL_SERVER)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LLMStreamWorkflow],
        activities=[stream_gpt],
    )

    # Start the worker in the background
    worker_task = asyncio.create_task(worker.run())

    try:
        # Execute the workflow
        handle = await client.start_workflow(
            LLMStreamWorkflow.run,
            message,
            id=WORKFLOW_ID,
            task_queue=TASK_QUEUE,
        )

        print("Workflow started...")
        print("Querying workflow for updated responses...\n")

        last_response = ""
        workflow_completed = False
        while True:
            try:
                response = await handle.query(LLMStreamWorkflow.get_response)
                new_content = response[len(last_response):]
                print(new_content, end="", flush=True)
                last_response = response

                if not workflow_completed:
                    # Check if the workflow has completed
                    try:
                        await asyncio.wait_for(handle.result(), timeout=0.1)
                        workflow_completed = True
                    except asyncio.TimeoutError:
                        # Workflow hasn't completed yet, continue querying
                        await asyncio.sleep(0.1)
                else:
                    # Workflow has completed, but we've printed the final chunk
                    break

            except Exception as e:
                print(f"\nAn error occurred: {e}")
                break

        print("\n\nWorkflow completed.")
        
        # Keep the worker running for 30 more seconds after workflow completion
        print("\nWorker will remain active for 30 seconds so you can query it.")
        for i in range(30, 0, -1):
            print(f"\rTime remaining: {i} seconds", end="", flush=True)
            await asyncio.sleep(1)

        print()  # Print a newline after the countdown

    finally:
        # Gracefully shutdown the worker
        print("Shutting down worker...")
        await worker.shutdown()

        # Cancel the worker task
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass  # This is expected, we can safely ignore it
        except Exception as e:
            print(f"Unexpected error during worker shutdown: {e}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Run LLM Stream Workflow using Temporal and OpenAI GPT",
        epilog="""
Example usage:
  poetry run python workflow.py "Give me a couple of paragraphs on the history of the Roman Empire."

Note: Make sure to set your OpenAI API key as an environment variable:
  export OPENAI_API_KEY=your_api_key_here

This script demonstrates a Temporal workflow that streams responses from 
OpenAI's GPT model. It provides real-time updates as the model generates 
the response, and keeps the Temporal worker running for a short period 
after completion to allow for potential queries.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("message", nargs="?", help="Message to send to the LLM (e.g., a question or prompt)")
    args = parser.parse_args()

    if not args.message:
        parser.print_help()
        return

    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set your OpenAI API key using:")
        print("  export OPENAI_API_KEY=your_api_key_here")
        return

    asyncio.run(run_workflow(args.message))


if __name__ == "__main__":
    main()
