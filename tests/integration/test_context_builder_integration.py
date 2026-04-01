import pytest
from unittest.mock import Mock
from application.services.context_builder import ContextBuilder
from domain.bible.entities.character import Character
from domain.bible.entities.character_registry import CharacterRegistry
from domain.bible.value_objects.character_id import CharacterId
from domain.bible.value_objects.character_importance import CharacterImportance
from domain.bible.value_objects.activity_metrics import ActivityMetrics
from domain.bible.services.appearance_scheduler import AppearanceScheduler
from domain.bible.services.relationship_engine import RelationshipEngine
from domain.bible.value_objects.relationship_graph import RelationshipGraph
from domain.novel.services.storyline_manager import StorylineManager
from domain.novel.entities.storyline import Storyline
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.storyline_type import StorylineType
from domain.novel.value_objects.storyline_status import StorylineStatus


class TestContextBuilderIntegration:
    """集成测试：上下文构建器完整流程"""

    def test_full_context_building_workflow(self):
        """测试完整的上下文构建工作流"""
        # 1. 设置角色注册表
        char_registry = CharacterRegistry(id="registry-1", novel_id="novel-1")

        # 注册主角
        protagonist = Character(
            CharacterId("char-1"),
            "Alice",
            "A brave warrior seeking revenge for her family"
        )
        char_registry.register_character(protagonist, CharacterImportance.PROTAGONIST)
        char_registry.update_activity(CharacterId("char-1"), chapter_number=5, dialogue_count=20)

        # 注册主要配角
        major_support = Character(
            CharacterId("char-2"),
            "Bob",
            "Alice's loyal companion and strategist"
        )
        char_registry.register_character(major_support, CharacterImportance.MAJOR_SUPPORTING)
        char_registry.update_activity(CharacterId("char-2"), chapter_number=4, dialogue_count=15)

        # 注册次要角色
        minor_char = Character(
            CharacterId("char-3"),
            "Charlie",
            "A merchant who provides information"
        )
        char_registry.register_character(minor_char, CharacterImportance.MINOR)

        # 2. 设置关系图
        relationship_graph = RelationshipGraph()
        relationship_engine = RelationshipEngine(relationship_graph)

        # 3. 设置故事线管理器
        storyline_repo = Mock()
        storyline = Storyline(
            id="storyline-1",
            novel_id=NovelId("novel-1"),
            storyline_type=StorylineType.MAIN_PLOT,
            status=StorylineStatus.ACTIVE,
            estimated_chapter_start=1,
            estimated_chapter_end=20
        )
        storyline_repo.get_by_novel_id.return_value = [storyline]

        storyline_manager = StorylineManager(storyline_repo)

        # 4. 设置其他依赖
        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        novel = Mock()
        novel.title = "The Quest for Vengeance"
        novel.author = "Test Author"
        novel_repo.get_by_id.return_value = novel

        # 模拟之前的章节
        prev_chapter = Mock()
        prev_chapter.number = 5
        prev_chapter.title = "The Betrayal"
        prev_chapter.content = "Alice discovered the truth about her family's death..."
        chapter_repo.list_by_novel.return_value = [prev_chapter]

        # 5. 创建上下文构建器
        context_builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # 6. 构建上下文
        outline = "Alice and Bob plan their next move against the enemy"
        context = context_builder.build_context(
            novel_id="novel-1",
            chapter_number=6,
            outline=outline,
            max_tokens=35000
        )

        # 7. 验证上下文内容
        assert "The Quest for Vengeance" in context
        assert "Chapter 6" in context
        assert "Alice" in context
        assert "Bob" in context
        assert "main_plot" in context.lower() or "MAIN_PLOT" in context
        assert "The Betrayal" in context  # 最近章节

        # 8. 验证 token 预算
        tokens = context_builder.estimate_tokens(context)
        assert tokens <= 35000

        # 9. 验证上下文结构
        assert "=== CONTEXT FOR CHAPTER GENERATION ===" in context
        assert "=== SMART RETRIEVAL ===" in context
        assert "=== RECENT CONTEXT ===" in context

    def test_appearance_scheduler_integration(self):
        """测试角色出场调度器集成"""
        # 创建角色
        char1 = Character(CharacterId("char1"), "Alice", "Protagonist")
        char2 = Character(CharacterId("char2"), "Bob", "Supporting")
        char3 = Character(CharacterId("char3"), "Charlie", "Minor")

        # 创建活动度指标
        metrics1 = ActivityMetrics()
        metrics1.update_activity(10, 5)

        metrics2 = ActivityMetrics()
        metrics2.update_activity(8, 3)

        metrics3 = ActivityMetrics()
        metrics3.update_activity(2, 1)

        # 可用角色列表
        available = [
            (char1, CharacterImportance.PROTAGONIST, metrics1),
            (char2, CharacterImportance.MAJOR_SUPPORTING, metrics2),
            (char3, CharacterImportance.MINOR, metrics3)
        ]

        # 调度器
        scheduler = AppearanceScheduler()

        # 大纲提到 Alice 和 Bob
        outline = "Alice and Bob discuss their strategy"
        selected = scheduler.schedule_appearances(outline, available, max_characters=2)

        # 验证
        assert len(selected) == 2
        assert char1 in selected
        assert char2 in selected
        assert char3 not in selected

    def test_context_builder_with_large_cast(self):
        """测试大规模角色的上下文构建"""
        # 创建大量角色
        char_registry = CharacterRegistry(id="registry-1", novel_id="novel-1")

        # 1 主角
        protagonist = Character(CharacterId("char-0"), "Hero", "The main character")
        char_registry.register_character(protagonist, CharacterImportance.PROTAGONIST)

        # 10 主要配角
        for i in range(1, 11):
            char = Character(
                CharacterId(f"char-{i}"),
                f"Support{i}",
                f"Supporting character {i}"
            )
            char_registry.register_character(char, CharacterImportance.MAJOR_SUPPORTING)

        # 50 次要角色
        for i in range(11, 61):
            char = Character(
                CharacterId(f"char-{i}"),
                f"Minor{i}",
                f"Minor character {i}"
            )
            char_registry.register_character(char, CharacterImportance.MINOR)

        # 设置依赖
        relationship_graph = RelationshipGraph()
        relationship_engine = RelationshipEngine(relationship_graph)

        storyline_manager = Mock()
        storyline_manager.repository.get_by_novel_id.return_value = []

        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        novel = Mock()
        novel.title = "Epic Tale"
        novel.author = "Author"
        novel_repo.get_by_id.return_value = novel

        chapter_repo.list_by_novel.return_value = []

        # 创建上下文构建器
        context_builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # 构建上下文
        context = context_builder.build_context(
            novel_id="novel-1",
            chapter_number=1,
            outline="Hero begins the journey",
            max_tokens=10000  # 较小的预算
        )

        # 验证
        tokens = context_builder.estimate_tokens(context)
        assert tokens <= 11000  # 允许 10% 误差
        assert "Hero" in context
        assert "Epic Tale" in context
