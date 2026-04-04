"""Mock LLM Provider for testing without API keys"""
import json
from typing import AsyncIterator
from domain.ai.value_objects.prompt import Prompt
from domain.ai.value_objects.token_usage import TokenUsage
from domain.ai.services.llm_service import GenerationConfig, GenerationResult, LLMService


class MockProvider(LLMService):
    """Mock LLM Provider for testing

    Returns predefined responses without calling any external API.
    """

    def __init__(self):
        """Initialize Mock Provider

        No settings or API key needed.
        """
        pass

    async def generate(
        self,
        prompt: Prompt,
        config: GenerationConfig
    ) -> GenerationResult:
        """Generate mock response

        Args:
            prompt: The prompt
            config: Generation config

        Returns:
            Mock generation result
        """
        # Detect what kind of generation is requested based on prompt
        user_prompt = prompt.user.lower()

        if "世界观" in user_prompt or "worldbuilding" in user_prompt:
            # Worldbuilding generation
            content = json.dumps({
                "style": "第三人称有限视角，以主角视角为主。基调轻松幽默，节奏明快。避免过度描写。营造轻松愉快的阅读氛围。",
                "worldbuilding": {
                    "core_rules": {
                        "power_system": "现代都市背景，无特殊力量体系",
                        "physics_rules": "遵循现实世界物理规律",
                        "magic_tech": "现代科技水平"
                    },
                    "geography": {
                        "terrain": "现代都市，高楼林立",
                        "climate": "温带季风气候，四季分明",
                        "resources": "现代城市资源丰富",
                        "ecology": "城市生态系统"
                    },
                    "society": {
                        "politics": "现代民主政体",
                        "economy": "市场经济",
                        "class_system": "现代社会阶层"
                    },
                    "culture": {
                        "history": "当代都市文化",
                        "religion": "多元信仰并存",
                        "taboos": "遵守现代社会规范"
                    },
                    "daily_life": {
                        "food_clothing": "现代都市生活方式",
                        "language_slang": "现代汉语，偶有网络用语",
                        "entertainment": "现代娱乐方式：电影、音乐、游戏等"
                    }
                }
            }, ensure_ascii=False)
        elif "人物" in user_prompt or "character" in user_prompt:
            # Character generation
            content = json.dumps({
                "characters": [
                    {
                        "name": "张三",
                        "role": "主角",
                        "description": "30岁，自由作家，性格开朗乐观，目标是写出畅销小说",
                        "relationships": [
                            {
                                "target": "李四",
                                "relation": "好友",
                                "description": "多年好友，互相支持"
                            }
                        ]
                    },
                    {
                        "name": "李四",
                        "role": "配角",
                        "description": "32岁，出版社编辑，性格严谨认真，帮助主角修改稿件",
                        "relationships": [
                            {
                                "target": "张三",
                                "relation": "好友",
                                "description": "多年好友，提供专业建议"
                            }
                        ]
                    },
                    {
                        "name": "王五",
                        "role": "对手",
                        "description": "28岁，畅销书作家，性格傲慢自负，与主角竞争",
                        "relationships": [
                            {
                                "target": "张三",
                                "relation": "竞争",
                                "description": "文学奖竞争对手"
                            }
                        ]
                    }
                ]
            }, ensure_ascii=False)
        elif "地点" in user_prompt or "location" in user_prompt:
            # Location generation
            content = json.dumps({
                "locations": [
                    {
                        "name": "咖啡馆",
                        "type": "建筑",
                        "description": "主角常去的咖啡馆，安静舒适，适合写作",
                        "connections": ["图书馆"]
                    },
                    {
                        "name": "图书馆",
                        "type": "建筑",
                        "description": "市中心图书馆，藏书丰富，主角查资料的地方",
                        "connections": ["咖啡馆", "出版社"]
                    },
                    {
                        "name": "出版社",
                        "type": "建筑",
                        "description": "李四工作的出版社，现代化办公楼",
                        "connections": ["图书馆"]
                    }
                ]
            }, ensure_ascii=False)
        else:
            # Default response
            content = json.dumps({
                "characters": [],
                "locations": [],
                "style": "第三人称视角，轻松基调"
            }, ensure_ascii=False)

        # Create mock token usage
        token_usage = TokenUsage(
            input_tokens=len(prompt.user),
            output_tokens=len(content)
        )

        return GenerationResult(content=content, token_usage=token_usage)

    async def stream_generate(
        self,
        prompt: Prompt,
        config: GenerationConfig
    ) -> AsyncIterator[str]:
        """Stream mock response

        Args:
            prompt: The prompt
            config: Generation config

        Yields:
            Mock response chunks
        """
        result = await self.generate(prompt, config)
        # Simulate streaming by yielding the content in chunks
        chunk_size = 50
        for i in range(0, len(result.content), chunk_size):
            yield result.content[i:i+chunk_size]
