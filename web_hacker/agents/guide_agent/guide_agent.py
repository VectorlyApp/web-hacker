"""
src/agents/guide_agent.py

Guide agent that guides the user through the process of creating or editing a routine.
"""

from data_models.llms import LLMModel, OpenAIModel
from data_models.routine.routine import Routine
from llms.llm_client import LLMClient
from llms.tools.guide_agent_tools import start_routine_discovery_job_creation
from utils.logger import get_logger


logger = get_logger(name=__name__)


class GuideAgent:
    """
    Guide agent that guides the user through the process of creating or editing a routine.
    """

    # Magic methods ________________________________________________________________________________________________________

    def __init__(
        self,
        llm_model: LLMModel = OpenAIModel.GPT_5_MINI,
    ) -> None:
        self.llm_model = llm_model
        self.llm_client = LLMClient(llm_model)
        self.llm_client.register_tool(
            name=start_routine_discovery_job_creation.__name__,
            description=start_routine_discovery_job_creation.__doc__,
            # TODO: FIXME: THIS IS NOT CORRECT AND WILL BREAK:
            parameters=start_routine_discovery_job_creation.model_json_schema(),
        )
        logger.info("Instantiated GuideAgent with model: %s", llm_model)


    # Public methods _______________________________________________________________________________________________________
