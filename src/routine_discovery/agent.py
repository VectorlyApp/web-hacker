import json
from pydantic import BaseModel, Field, field_validator
from openai import OpenAI
from src.routine_discovery.context_manager import ContextManager
from src.utils.llm_utils import llm_parse_text_to_model, collect_text_from_response
from src.data_models.llm_responses import (
    TransactionIdentificationResponse,
    ExtractedVariableResponse,
    TransactionConfirmationResponse,
)
from uuid import uuid4
import os


class RoutineDiscoveryAgent(BaseModel):
    """
    Agent for discovering routines from the network transactions.
    """
    client: OpenAI
    context_manager: ContextManager
    task_description: str
    llm_model: str = "gpt-5-mini"
    message_history: list[dict] = Field(default_factory=list)
    debug_dir: str
    last_response_id: str | None = None
    tools: list[dict] = Field(default_factory=list)
    n_transaction_identification_attempts: int = 3
    current_transaction_identification_attempt: int = 0
    
    class Config:
        arbitrary_types_allowed = True
        
    SYSTEM_PROMPT_IDENTIFY_TRANSACTIONS: str = f"""
    You are a helpful assistant that is an expert in parsing network traffic.
    You need to identify one or more network transactions that directly correspond to the user's requested task.
    You have access to vectorstore that contains network transactions and storage data
    (cookies, localStorage, sessionStorage, etc.).
    """
        
        
    def run(self) -> None:
        """
        Run the routine discovery agent.
        """
        
        # make the output dir if specified
        os.makedirs(self.debug_dir, exist_ok=True)
        
        # validate the context manager
        assert self.context_manager.vectorstore_id is not None, "Vectorstore ID is not set"
        
        # construct the tools
        self.tools = [
            {
                "type": "file_search",
                "vector_store_ids": [self.context_manager.vectorstore_id],
            }
        ]
        
        # add the system prompt to the message history
        self.add_to_message_history("system", self.SYSTEM_PROMPT_IDENTIFY_TRANSACTIONS)
        
        # add the user prompt to the message history
        self.add_to_message_history("user", f"Task description: {self.task_description}")
        
        self.add_to_message_history("user", f"These are the possible network transaction ids you can choose from: {self.context_manager.get_all_transaction_ids()}")

        # Step 1: Identify the network transactions that directly correspond to the user's requested task
        identified_transactions = None
        
        while identified_transactions is None:
            # identify the transactions
            identified_transactions = self.identify_transactions()
            
            # confirm the identified transactions
            confirmation_response = self.confirm_indetified_transactions(identified_transactions)
            
            # if the identified transactions are not correct, try again
            if not confirmation_response.is_correct:
                identified_transactions = None
                self.current_transaction_identification_attempt += 1
                
        if identified_transactions is None:
            raise Exception("Failed to identify the network transactions that directly correspond to the user's requested task.")
        
        # save the indentified transactions
        with open(os.path.join(self.debug_dir, "identified_transactions.json"), "w") as f:
            json.dump(identified_transactions.model_dump(), f, ensure_ascii=False, indent=2)
        
        # Step 2: Extract the variables from the identified transactions
        extracted_variables = self.extract_variables(identified_transactions)
        
        with open(os.path.join(self.debug_dir, "extracted_variables.json"), "w") as f:
            json.dump(extracted_variables.model_dump(), f, ensure_ascii=False, indent=2)
        
        
    def identify_transactions(self) -> TransactionIdentificationResponse:
        """
        Identify the network transactions that directly correspond to the user's requested task.
        """
        if self.current_transaction_identification_attempt == 0:
            self.message_history = [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT_IDENTIFY_TRANSACTIONS
                },
                {
                    "role": "user",
                    "content": f"Task description: {self.task_description}"
                },
                {
                    "role": "user",
                    "content": f"These are the possible network transaction ids you can choose from: {self.context_manager.get_all_transaction_ids()}"
                },
                {
                    "role": "user",
                    "content": f"Please respond in the following format: {TransactionIdentificationResponse.model_json_schema()}"
                }
            ]
        else:
            message = (
                f"Please try again to identify the network transactions that directly correspond to the user's requested task."
                f"Respond in the following format: {TransactionIdentificationResponse.model_json_schema()}"
            )
            self.add_to_message_history("user", message)
        
        # call to the LLM API
        response = self.client.responses.create(
            model=self.llm_model,
            input=self.message_history if self.current_transaction_identification_attempt == 0 else [self.message_history[-1]],
            previous_response_id=self.last_response_id,
            tools=self.tools,
            tool_choice="required",
        )
        
        # save the response id
        self.last_response_id = response.id
        
        # collect the text from the response
        response_text = collect_text_from_response(response)
        self.add_to_message_history("assistant", response_text)
        
        # parse the response to the pydantic model
        parsed_response = llm_parse_text_to_model(
            text=response_text,
            context="\n".join([f"{msg['role']}: {msg['content']}" for msg in self.message_history[-3:]]),
            pydantic_model=TransactionIdentificationResponse,
            client=self.client,
            llm_model=self.llm_model
        )
        self.add_to_message_history("assistant", parsed_response.model_dump_json())
        
        # return the parsed response
        return parsed_response


    def confirm_indetified_transactions(
        self,
        identified_transactions: TransactionIdentificationResponse,
    ) -> TransactionConfirmationResponse:
        """
        Confirm the identified network transactions that directly correspond to the user's requested task.
        """
        
        # add the transactions to the vectorstore
        metadata = {"uuid": str(uuid4())}
        for transaction_id in identified_transactions.transaction_ids:
            self.context_manager.add_transaction_to_vectorstore(transaction_id=transaction_id, metadata=metadata)
        
        # temporarily update the tools to specifically search through these transactions
        tools = [
            {
                "type": "file_search",
                "vector_store_ids": [self.context_manager.vectorstore_id],
                "filters": {
                    "type": "eq",
                    "key": "uuid",
                    "value": [metadata["uuid"]]
                }
            }
        ]
        
        # update the message history with request to confirm the identified transactions
        message = (
            f"{identified_transactions} have been added to the vectorstore in full (including response bodies)."
            "Please confirm that the identified transactions are correct and that they directly correspond to the user's requested task:"
            f"{self.task_description}"
            f"Please respond in the following format: {TransactionConfirmationResponse.model_json_schema()}"
        )
        self.add_to_message_history("user", f"Please confirm that the identified transactions are correct. {identified_transactions.model_dump_json()}")
        
        # call to the LLM API for confirmation that the identified transactions are correct
        response = self.client.responses.create(
            model=self.llm_model,
            input=[self.message_history[-1]],
            previous_response_id=self.last_response_id,
            tools=tools,
            tool_choice="required", # forces the LLM to look at the newly added files to the vectorstore
        )
        
        # save the response id
        self.last_response_id = response.id
        
        # collect the text from the response
        response_text = collect_text_from_response(response)
        self.add_to_message_history("assistant", response_text)
        
        # parse the response to the pydantic model
        parsed_response = llm_parse_text_to_model(
            text=response_text,
            context="\n".join([f"{msg['role']}: {msg['content']}" for msg in self.message_history[-3:]]),
            pydantic_model=TransactionConfirmationResponse,
            client=self.client,
            llm_model=self.llm_model
        )
        
        return parsed_response
    
    
    def extract_variables(
        self,
        identified_transactions: TransactionIdentificationResponse,
    ) -> ExtractedVariableResponse:
        """
        Extract the variables from the identified transactions.
        """
        
        # get the requests of the identified transactions
        requests = []
        for transaction_id in identified_transactions.transaction_ids:
            request = self.context_manager.get_transaction_by_id(transaction_id)
            requests.append(request)
        
        # add message to the message history
        message = (
            f"Please extract the variables from the requests of identified network transactions:"
            f"{requests}"
            f"Please respond in the following format: {ExtractedVariableResponse.model_json_schema()}"
        )
        self.add_to_message_history("user", message)
        
        # call to the LLM API for extraction of the variables
        response = self.client.responses.create(
            model=self.llm_model,
            input=[self.message_history[-1]],
            previous_response_id=self.last_response_id,
            tools=self.tools,
            tool_choice="auto",
        )
        
        # save the response id
        self.last_response_id = response.id
        
        # collect the text from the response
        response_text = collect_text_from_response(response)
        self.message_history.append({"role": "assistant","content": response_text})
        
        # parse the response to the pydantic model
        parsed_response = llm_parse_text_to_model(
            text=response_text,
            context="\n".join([f"{msg['role']}: {msg['content']}" for msg in self.message_history[-3:]]),
            pydantic_model=ExtractedVariableResponse,
            client=self.client,
            llm_model=self.llm_model
        )
        self.add_to_message_history("assistant", parsed_response.model_dump_json())
        
        return parsed_response
    

    def add_to_message_history(self, role: str, content: str) -> None:
        self.message_history.append({"role": role, "content": content})
        with open(os.path.join(self.debug_dir, "message_history.json"), "w") as f:
            json.dump(self.message_history, f, ensure_ascii=False, indent=2)