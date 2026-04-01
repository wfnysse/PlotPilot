import pytest
from unittest.mock import Mock, MagicMock
from application.services.context_builder import ContextBuilder
from domain.bible.entities.character import Character
from domain.bible.entities.character_registry import CharacterRegistry
from domain.bible.value_objects.character_id import CharacterId
from domain.bible.value_objects.character_importance import CharacterImportance
from domain.bible.value_objects.activity_metrics import ActivityMetrics
from domain.novel.entities.storyline import Storyline
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.storyline_type import StorylineType
from domain.novel.value_objects.storyline_status import StorylineStatus
from domain.novel.value_objects.event_timeline import EventTimeline
from domain.novel.value_objects.novel_event import NovelEvent
from domain.bible.value_objects.relationship_graph import RelationshipGraph


class TestContextBuilder:
    """测试上下文构建器"""

    def test_estimate_tokens(self):
        """测试 token 估算"""
        builder = ContextBuilder(
            character_registry=Mock(),
            storyline_manager=Mock(),
            relationship_engine=Mock(),
            vector_store=Mock(),
            novel_repository=Mock(),
            chapter_repository=Mock()
        )

        # 1 token ≈ 4 chars
        text = "a" * 400  # 400 chars
        tokens = builder.estimate_tokens(text)
        assert 90 <= tokens <= 110  # Should be around 100 tokens

    def test_build_context_basic(self):
        """测试基本上下文构建"""
        # Arrange
        char_registry = Mock(spec=CharacterRegistry)
        char_registry.novel_id = "novel-1"

        storyline_manager = Mock()
        relationship_engine = Mock()
        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        # Mock novel
        novel = Mock()
        novel.title = "Test Novel"
        novel.author = "Test Author"
        novel_repo.get_by_id.return_value = novel

        # Mock storylines
        storyline = Mock(spec=Storyline)
        storyline.storyline_type = StorylineType.MAIN_PLOT
        storyline.status = StorylineStatus.ACTIVE
        storyline.estimated_chapter_start = 1
        storyline.estimated_chapter_end = 10
        storyline.get_pending_milestones.return_value = []
        storyline_manager.repository.get_by_novel_id.return_value = [storyline]

        # Mock characters
        char1 = Character(CharacterId("char1"), "Alice", "Protagonist")
        char_registry.get_characters_for_context.return_value = [char1]
        char_registry.characters_by_importance = {
            CharacterImportance.PROTAGONIST: [char1]
        }

        # Mock chapters
        chapter_repo.list_by_novel.return_value = []

        # Mock relationship graph
        relationship_engine._graph = RelationshipGraph()

        builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # Act
        context = builder.build_context(
            novel_id="novel-1",
            chapter_number=1,
            outline="Alice starts her journey",
            max_tokens=35000
        )

        # Assert
        assert "Test Novel" in context
        assert "Alice" in context
        assert "Chapter 1" in context

    def test_build_context_respects_token_budget(self):
        """测试遵守 token 预算"""
        # Arrange
        char_registry = Mock(spec=CharacterRegistry)
        char_registry.novel_id = "novel-1"

        storyline_manager = Mock()
        relationship_engine = Mock()
        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        # Mock novel
        novel = Mock()
        novel.title = "Test Novel"
        novel.author = "Test Author"
        novel_repo.get_by_id.return_value = novel

        # Mock storylines
        storyline_manager.repository.get_by_novel_id.return_value = []

        # Mock many characters with long descriptions
        chars = []
        for i in range(100):
            char = Character(
                CharacterId(f"char{i}"),
                f"Character{i}",
                "Very long description " * 100  # Long description
            )
            chars.append(char)

        char_registry.get_characters_for_context.return_value = chars[:10]
        char_registry.characters_by_importance = {
            CharacterImportance.PROTAGONIST: chars[:10]
        }

        # Mock chapters
        chapter_repo.list_by_novel.return_value = []

        # Mock relationship graph
        relationship_engine._graph = RelationshipGraph()

        builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # Act
        context = builder.build_context(
            novel_id="novel-1",
            chapter_number=1,
            outline="Test outline",
            max_tokens=5000  # Small budget
        )

        # Assert
        tokens = builder.estimate_tokens(context)
        assert tokens <= 5500  # Allow 10% margin

    def test_build_context_includes_recent_chapters(self):
        """测试包含最近章节"""
        # Arrange
        char_registry = Mock(spec=CharacterRegistry)
        char_registry.novel_id = "novel-1"

        storyline_manager = Mock()
        relationship_engine = Mock()
        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        # Mock novel
        novel = Mock()
        novel.title = "Test Novel"
        novel.author = "Test Author"
        novel_repo.get_by_id.return_value = novel

        # Mock storylines
        storyline_manager.repository.get_by_novel_id.return_value = []

        # Mock characters
        char_registry.get_characters_for_context.return_value = []
        char_registry.characters_by_importance = {}

        # Mock recent chapters
        chapter1 = Mock()
        chapter1.number = 1
        chapter1.title = "Chapter 1"
        chapter1.content = "Content of chapter 1"

        chapter2 = Mock()
        chapter2.number = 2
        chapter2.title = "Chapter 2"
        chapter2.content = "Content of chapter 2"

        chapter_repo.list_by_novel.return_value = [chapter1, chapter2]

        # Mock relationship graph
        relationship_engine._graph = RelationshipGraph()

        builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # Act
        context = builder.build_context(
            novel_id="novel-1",
            chapter_number=3,
            outline="Test outline",
            max_tokens=35000
        )

        # Assert
        assert "Chapter 1" in context or "Chapter 2" in context

    def test_build_context_includes_storylines(self):
        """测试包含故事线信息"""
        # Arrange
        char_registry = Mock(spec=CharacterRegistry)
        char_registry.novel_id = "novel-1"

        storyline_manager = Mock()
        relationship_engine = Mock()
        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        # Mock novel
        novel = Mock()
        novel.title = "Test Novel"
        novel.author = "Test Author"
        novel_repo.get_by_id.return_value = novel

        # Mock active storyline
        storyline = Mock(spec=Storyline)
        storyline.storyline_type = StorylineType.MAIN_PLOT
        storyline.status = StorylineStatus.ACTIVE
        storyline.estimated_chapter_start = 1
        storyline.estimated_chapter_end = 10
        storyline.get_pending_milestones.return_value = []
        storyline_manager.repository.get_by_novel_id.return_value = [storyline]

        # Mock characters
        char_registry.get_characters_for_context.return_value = []
        char_registry.characters_by_importance = {}

        # Mock chapters
        chapter_repo.list_by_novel.return_value = []

        # Mock relationship graph
        relationship_engine._graph = RelationshipGraph()

        builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # Act
        context = builder.build_context(
            novel_id="novel-1",
            chapter_number=5,
            outline="Test outline",
            max_tokens=35000
        )

        # Assert
        assert "MAIN" in context or "main" in context.lower()
        assert "ACTIVE" in context or "active" in context.lower()

    def test_build_context_performance(self):
        """测试上下文构建性能（应该 < 2 秒）"""
        import time

        # Arrange
        char_registry = Mock(spec=CharacterRegistry)
        char_registry.novel_id = "novel-1"

        storyline_manager = Mock()
        relationship_engine = Mock()
        vector_store = Mock()
        novel_repo = Mock()
        chapter_repo = Mock()

        # Mock novel
        novel = Mock()
        novel.title = "Test Novel"
        novel.author = "Test Author"
        novel_repo.get_by_id.return_value = novel

        # Mock storylines
        storyline_manager.repository.get_by_novel_id.return_value = []

        # Mock many characters
        chars = []
        for i in range(1000):
            char = Character(
                CharacterId(f"char{i}"),
                f"Character{i}",
                f"Description {i}"
            )
            chars.append(char)

        char_registry.get_characters_for_context.return_value = chars[:50]
        char_registry.characters_by_importance = {
            CharacterImportance.PROTAGONIST: chars[:50]
        }

        # Mock chapters
        chapters = []
        for i in range(100):
            chapter = Mock()
            chapter.number = i + 1
            chapter.title = f"Chapter {i+1}"
            chapter.content = f"Content of chapter {i+1}" * 100
            chapters.append(chapter)
        chapter_repo.list_by_novel.return_value = chapters

        # Mock relationship graph
        relationship_engine._graph = RelationshipGraph()

        builder = ContextBuilder(
            character_registry=char_registry,
            storyline_manager=storyline_manager,
            relationship_engine=relationship_engine,
            vector_store=vector_store,
            novel_repository=novel_repo,
            chapter_repository=chapter_repo
        )

        # Act
        start_time = time.time()
        context = builder.build_context(
            novel_id="novel-1",
            chapter_number=50,
            outline="Test outline",
            max_tokens=35000
        )
        elapsed_time = time.time() - start_time

        # Assert
        assert elapsed_time < 2.0  # Should be < 2 seconds
        assert len(context) > 0
