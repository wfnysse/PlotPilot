"""Bible API 路由"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Union, Dict, Any
import logging

from application.world.services.bible_service import BibleService
from application.world.services.auto_bible_generator import AutoBibleGenerator
from application.world.services.auto_knowledge_generator import AutoKnowledgeGenerator
from application.world.dtos.bible_dto import BibleDTO
from interfaces.api.dependencies import (
    get_bible_service,
    get_auto_bible_generator,
    get_auto_knowledge_generator
)
from domain.shared.exceptions import EntityNotFoundError

logger = logging.getLogger(__name__)


def _get_bible_repository():
    """获取 Bible Repository 实例（辅助函数）"""
    from infrastructure.persistence.database.sqlite_bible_repository import SqliteBibleRepository
    from infrastructure.persistence.database.connection import DatabaseConnection
    from application.paths import get_db_path
    
    db_path = get_db_path()
    db = DatabaseConnection(db_path)
    return SqliteBibleRepository(db)


router = APIRouter(prefix="/bible", tags=["bible"])


# Request Models
class CreateBibleRequest(BaseModel):
    """创建 Bible 请求"""
    bible_id: str = Field(..., description="Bible ID")
    novel_id: str = Field(..., description="小说 ID")


class AddCharacterRequest(BaseModel):
    """添加人物请求"""
    character_id: str = Field(..., description="人物 ID")
    name: str = Field(..., description="人物名称")
    description: str = Field(..., description="人物描述")


class AddWorldSettingRequest(BaseModel):
    """添加世界设定请求"""
    setting_id: str = Field(..., description="设定 ID")
    name: str = Field(..., description="设定名称")
    description: str = Field(..., description="设定描述")
    setting_type: str = Field(..., description="设定类型")


class AddLocationRequest(BaseModel):
    """添加地点请求"""
    location_id: str = Field(..., description="地点 ID")
    name: str = Field(..., description="地点名称")
    description: str = Field(..., description="地点描述")
    location_type: str = Field(..., description="地点类型")
    parent_id: Optional[str] = Field(default=None, description="父地点 id，根为 null")


class AddTimelineNoteRequest(BaseModel):
    """添加时间线笔记请求"""
    note_id: str = Field(..., description="笔记 ID")
    event: str = Field(..., description="事件")
    time_point: str = Field(..., description="时间点")
    description: str = Field(..., description="描述")


class AddStyleNoteRequest(BaseModel):
    """添加风格笔记请求"""
    note_id: str = Field(..., description="笔记 ID")
    category: str = Field(..., description="类别")
    content: str = Field(..., description="内容")


class BibleCharacterRelationshipItem(BaseModel):
    """Bible 人物关系项（与 LLM 输出的 target/relation/description 对象一致）"""

    model_config = ConfigDict(extra="allow")

    target: Optional[str] = None
    relation: Optional[str] = None
    description: Optional[str] = None


class CharacterData(BaseModel):
    """人物数据（角色卡）"""
    id: str = Field(..., description="人物 ID")
    name: str = Field(..., description="人物名称")
    description: str = Field(..., description="人物描述")
    relationships: list[Union[str, BibleCharacterRelationshipItem]] = Field(
        default_factory=list,
        description="关系列表：字符串或结构化对象",
    )
    mental_state: Optional[str] = Field(
        default=None,
        description="心理状态；省略则保留库中旧值（新角色默认 NORMAL）",
    )
    verbal_tic: Optional[str] = Field(default=None, description="口头禅；省略则保留库中旧值")
    idle_behavior: Optional[str] = Field(
        default=None,
        description="待机动作/小动作；省略则保留库中旧值",
    )
    
    # 【角色卡扩展】基本信息
    role: Optional[str] = Field(default=None, description="角色定位：主角/配角/反派/导师等")
    gender: Optional[str] = Field(default=None, description="性别")
    age: Optional[str] = Field(default=None, description="年龄")
    identity: Optional[str] = Field(default=None, description="身份/职业")
    appearance: Optional[str] = Field(default=None, description="外貌特征")
    
    # 【角色卡扩展】性格特征
    personality: Optional[str] = Field(default=None, description="性格关键词")
    strengths: Optional[str] = Field(default=None, description="优点")
    weaknesses: Optional[str] = Field(default=None, description="缺点")
    habits: Optional[str] = Field(default=None, description="行为习惯")
    
    # 【角色卡扩展】背景故事
    background: Optional[str] = Field(default=None, description="背景故事")
    motivation: Optional[str] = Field(default=None, description="动机")
    goal: Optional[str] = Field(default=None, description="目标")
    
    # 【角色卡扩展】能力体系
    power_system: Optional[str] = Field(default=None, description="力量体系/能力")
    skills: Optional[str] = Field(default=None, description="技能")
    equipment: Optional[str] = Field(default=None, description="装备/道具")
    
    # 【角色卡扩展】发展轨迹
    character_arc: Optional[str] = Field(default=None, description="角色弧光/成长路线")


class WorldSettingData(BaseModel):
    """世界设定数据"""
    id: str = Field(..., description="设定 ID")
    name: str = Field(..., description="设定名称")
    description: str = Field(..., description="设定描述")
    setting_type: str = Field(..., description="设定类型")


class LocationData(BaseModel):
    """地点数据"""
    id: str = Field(..., description="地点 ID")
    name: str = Field(..., description="地点名称")
    description: str = Field(..., description="地点描述")
    location_type: str = Field(..., description="地点类型")
    parent_id: Optional[str] = Field(default=None, description="父地点 id，根为 null")


class TimelineNoteData(BaseModel):
    """时间线笔记数据"""
    id: str = Field(..., description="笔记 ID")
    event: str = Field(..., description="事件")
    time_point: str = Field(..., description="时间点")
    description: str = Field(..., description="描述")


class StyleNoteData(BaseModel):
    """风格笔记数据"""
    id: str = Field(..., description="笔记 ID")
    category: str = Field(..., description="类别")
    content: str = Field(..., description="内容")


class BulkUpdateBibleRequest(BaseModel):
    """批量更新 Bible 请求"""
    characters: list[CharacterData] = Field(default_factory=list, description="人物列表")
    world_settings: list[WorldSettingData] = Field(default_factory=list, description="世界设定列表")
    locations: list[LocationData] = Field(default_factory=list, description="地点列表")
    timeline_notes: list[TimelineNoteData] = Field(default_factory=list, description="时间线笔记列表")
    style_notes: list[StyleNoteData] = Field(default_factory=list, description="风格笔记列表")


# Routes
@router.post("/novels/{novel_id}/generate", status_code=202)
async def generate_bible(
    novel_id: str,
    background_tasks: BackgroundTasks,
    stage: str = "all",  # all / worldbuilding / characters / locations
    bible_generator: AutoBibleGenerator = Depends(get_auto_bible_generator),
    knowledge_generator: AutoKnowledgeGenerator = Depends(get_auto_knowledge_generator)
):
    """手动触发 Bible 和 Knowledge 生成（异步）

    支持分阶段生成：
    - stage=all: 一次性生成所有内容（默认，向后兼容）
    - stage=worldbuilding: 只生成世界观（5维度）和文风公约
    - stage=characters: 基于已有世界观生成人物
    - stage=locations: 基于已有世界观和人物生成地点

    用户创建小说后，前端调用此接口开始生成 Bible。
    生成过程在后台进行，前端应轮询 /bible/novels/{novel_id}/bible/status 检查状态。

    Args:
        novel_id: 小说 ID
        stage: 生成阶段
        background_tasks: FastAPI 后台任务
        bible_generator: Bible 生成器
        knowledge_generator: Knowledge 生成器

    Returns:
        202 Accepted，表示生成任务已启动
    """
    import sys
    print(f"[API START] generate_bible called for novel_id={novel_id}, stage={stage}", file=sys.stderr, flush=True)
    logger.info(f"[API] generate_bible endpoint called for novel_id={novel_id}, stage={stage}")
    
    async def _generate_task():
        import sys
        print(f"[TASK START] Bible generation for {novel_id}, stage={stage}", file=sys.stderr, flush=True)
        logger.info(f"Starting Bible generation task for {novel_id}, stage={stage}")
        try:
            # 获取小说信息（需要 premise 和 target_chapters）
            from interfaces.api.dependencies import get_novel_service
            novel_service = get_novel_service()
            novel = novel_service.get_novel(novel_id)
            if not novel:
                logger.error(f"Novel not found: {novel_id}")
                return

            # 使用 premise（故事梗概）生成 Bible，如果没有则使用 title
            premise = novel.premise if novel.premise else novel.title
            logger.info(f"Novel premise: {premise[:100]}...")

            # 生成 Bible（支持分阶段）
            logger.info(f"Calling bible_generator.generate_and_save...")
            bible_data = await bible_generator.generate_and_save(
                novel_id,
                premise,
                novel.target_chapters,
                stage=stage
            )
            logger.info(f"generate_and_save completed successfully")

            # 构建 Bible 摘要供 Knowledge 生成使用
            chars = bible_data.get("characters", [])
            locs = bible_data.get("locations", [])
            char_desc = "、".join(f"{c['name']}（{c.get('role', '')}）" for c in chars[:5])
            loc_desc = "、".join(c['name'] for c in locs[:3])
            bible_summary = f"主要角色：{char_desc}。重要地点：{loc_desc}。文风：{bible_data.get('style', '')}。"

            # 生成初始 Knowledge
            await knowledge_generator.generate_and_save(
                novel_id,
                novel.title,
                bible_summary
            )
            logger.info(f"Bible and Knowledge generated successfully for {novel_id}")
        except Exception as e:
            import sys
            import traceback
            print(f"[TASK ERROR] {e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            logger.error(f"Failed to generate Bible/Knowledge for {novel_id}: {e}")
            logger.error(traceback.format_exc())

    background_tasks.add_task(_generate_task)
    logger.info(f"[API] Background task added for novel_id={novel_id}")

    return {
        "message": "Bible generation started",
        "novel_id": novel_id,
        "status_url": f"/api/v1/bible/novels/{novel_id}/bible/status"
    }


@router.post("/novels/{novel_id}/bible/characters/confirm")
async def confirm_characters(
    novel_id: str,
    request: Dict[str, Any],
    bible_generator: AutoBibleGenerator = Depends(get_auto_bible_generator)
):
    """确认并保存角色，生成完整角色卡
    
    Args:
        novel_id: 小说 ID
        request: {
            "characters": [...],  # 用户确认的角色列表
            "generate_full_card": true  # 是否生成完整角色卡
        }
        bible_generator: Bible 生成器
        
    Returns:
        保存结果
    """
    try:
        characters = request.get("characters", [])
        generate_full_card = request.get("generate_full_card", True)
        
        if not characters:
            raise HTTPException(
                status_code=400,
                detail="No characters provided"
            )
        
        logger.info(f"Confirming {len(characters)} characters for {novel_id}")
        
        result = await bible_generator.confirm_and_save_characters(
            novel_id=novel_id,
            characters=characters,
            generate_full_card=generate_full_card
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to confirm characters: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to confirm characters: {str(e)}"
        )


@router.post("/novels/{novel_id}/bible", response_model=BibleDTO, status_code=201)
async def create_bible(
    novel_id: str,
    request: CreateBibleRequest,
    service: BibleService = Depends(get_bible_service)
):
    """为小说创建 Bible

    Args:
        novel_id: 小说 ID
        request: 创建 Bible 请求
        service: Bible 服务

    Returns:
        创建的 Bible DTO
    """
    return service.create_bible(request.bible_id, novel_id)


# 注意：必须先注册比 `/novels/{id}/bible` 更长的路径，避免与 `{novel_id}` 匹配歧义
@router.get("/novels/{novel_id}/bible/status")
async def get_bible_status(
    novel_id: str,
    service: BibleService = Depends(get_bible_service)
):
    """检查 Bible 生成状态

    Args:
        novel_id: 小说 ID
        service: Bible 服务

    Returns:
        状态信息：{ "exists": bool, "ready": bool }
    """
    try:
        bible = service.get_bible_by_novel(novel_id)
        exists = bible is not None
        # 修改ready逻辑：只要有文风公约或世界观就算ready（支持分阶段生成）
        ready = exists and (len(bible.style_notes) > 0 or len(bible.world_settings) > 0 or len(bible.characters) > 0)

        return {
            "exists": exists,
            "ready": ready,
            "novel_id": novel_id
        }
    except Exception as e:
        logger.exception("get_bible_status failed for novel_id=%s", novel_id)
        raise HTTPException(status_code=500, detail=f"检查 Bible 状态失败: {e}") from e


@router.get("/novels/{novel_id}/generate/progress")
async def get_generation_progress(
    novel_id: str
):
    """获取 Bible 生成实时进度

    Args:
        novel_id: 小说 ID

    Returns:
        进度信息：{ "novel_id": str, "stage": str, "current_step": int, "total_steps": int, "message": str, "progress": float, "updated_at": str }
        如果没有进行中的生成任务，返回 { "progress": null }
    """
    from application.world.services.auto_bible_generator import get_bible_progress
    progress = get_bible_progress(novel_id)
    
    if progress is None:
        return {"progress": None}
    
    return {"progress": progress}


@router.get("/novels/{novel_id}/bible", response_model=BibleDTO)
async def get_bible_by_novel(
    novel_id: str,
    service: BibleService = Depends(get_bible_service)
):
    """获取小说的 Bible

    Args:
        novel_id: 小说 ID
        service: Bible 服务

    Returns:
        Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    bible = service.get_bible_by_novel(novel_id)
    if bible is None:
        raise HTTPException(
            status_code=404,
            detail=f"Bible not found for novel: {novel_id}"
        )
    return bible


@router.get("/novels/{novel_id}/bible/characters", response_model=list)
async def list_characters(
    novel_id: str,
    service: BibleService = Depends(get_bible_service)
):
    """列出 Bible 中的所有人物

    Args:
        novel_id: 小说 ID
        service: Bible 服务

    Returns:
        人物 DTO 列表

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    bible = service.get_bible_by_novel(novel_id)
    if bible is None:
        raise HTTPException(
            status_code=404,
            detail=f"Bible not found for novel: {novel_id}"
        )
    return bible.characters


@router.post("/novels/{novel_id}/bible/characters", response_model=BibleDTO)
async def add_character(
    novel_id: str,
    request: AddCharacterRequest,
    service: BibleService = Depends(get_bible_service)
):
    """添加人物到 Bible

    Args:
        novel_id: 小说 ID
        request: 添加人物请求
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    try:
        return service.add_character(
            novel_id=novel_id,
            character_id=request.character_id,
            name=request.name,
            description=request.description
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/novels/{novel_id}/bible/characters/{character_id}", response_model=BibleDTO)
async def update_character(
    novel_id: str,
    character_id: str,
    request: CharacterData,
    service: BibleService = Depends(get_bible_service)
):
    """更新角色卡信息

    Args:
        novel_id: 小说 ID
        character_id: 角色 ID
        request: 角色卡数据（包含所有扩展字段）
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 或角色不存在
    """
    try:
        bible = service.get_bible_by_novel(novel_id)
        if bible is None:
            raise HTTPException(
                status_code=404,
                detail=f"Bible not found for novel: {novel_id}"
            )
        
        # 查找角色
        character = None
        for char in bible.characters:
            if char.character_id.value == character_id or char.name == character_id:
                character = char
                break
        
        if character is None:
            raise HTTPException(
                status_code=404,
                detail=f"Character not found: {character_id}"
            )
        
        # 更新基本字段
        if request.name is not None:
            character.name = request.name
        if request.description is not None:
            character.description = request.description
        if request.relationships is not None:
            character.relationships = request.relationships
        if request.mental_state is not None:
            character.mental_state = request.mental_state
        if request.verbal_tic is not None:
            character.verbal_tic = request.verbal_tic
        if request.idle_behavior is not None:
            character.idle_behavior = request.idle_behavior
        
        # 【角色卡扩展】更新基本信息
        if request.role is not None:
            character.role = request.role
        if request.gender is not None:
            character.gender = request.gender
        if request.age is not None:
            character.age = request.age
        if request.identity is not None:
            character.identity = request.identity
        if request.appearance is not None:
            character.appearance = request.appearance
        
        # 【角色卡扩展】更新性格特征
        if request.personality is not None:
            character.personality = request.personality
        if request.strengths is not None:
            character.strengths = request.strengths
        if request.weaknesses is not None:
            character.weaknesses = request.weaknesses
        if request.habits is not None:
            character.habits = request.habits
        
        # 【角色卡扩展】更新背景故事
        if request.background is not None:
            character.background = request.background
        if request.motivation is not None:
            character.motivation = request.motivation
        if request.goal is not None:
            character.goal = request.goal
        
        # 【角色卡扩展】更新能力体系
        if request.power_system is not None:
            character.power_system = request.power_system
        if request.skills is not None:
            character.skills = request.skills
        if request.equipment is not None:
            character.equipment = request.equipment
        
        # 【角色卡扩展】更新发展轨迹
        if request.character_arc is not None:
            character.character_arc = request.character_arc
        
        # 保存 Bible
        repo = _get_bible_repository()
        repo.save(bible)
        
        logger.info(f"Updated character card: {character.name} ({character_id})")
        return bible
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update character: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update character: {str(e)}"
        )


@router.post("/novels/{novel_id}/bible/characters/{character_id}/complete")
async def complete_character_card(
    novel_id: str,
    character_id: str,
    request: Dict[str, Any],
    bible_generator: AutoBibleGenerator = Depends(get_auto_bible_generator),
    bible_service: BibleService = Depends(get_bible_service)
):
    """使用 AI 补全角色卡的完整资料
    
    Args:
        novel_id: 小说 ID
        character_id: 角色 ID
        request: 请求数据（可选）
        bible_generator: Bible 生成器
        bible_service: Bible 服务
        
    Returns:
        补全后的角色数据
    """
    try:
        # 1. 获取 Bible 领域实体（不是 DTO）
        repo = _get_bible_repository()
        from domain.novel.value_objects.novel_id import NovelId
        
        bible = repo.get_by_novel_id(NovelId(novel_id))
        
        if bible is None:
            raise HTTPException(
                status_code=404,
                detail=f"Bible not found for novel: {novel_id}"
            )
        
        # 2. 查找角色（bible.characters 是 Character 领域实体列表）
        character = None
        for char in bible.characters:
            # 领域实体使用 character_id 属性（ValueObject）
            if char.character_id.value == character_id or char.name == character_id:
                character = char
                break
        
        if character is None:
            raise HTTPException(
                status_code=404,
                detail=f"Character not found: {character_id}"
            )
        
        # 3. 加载世界观
        existing_worldbuilding = bible_generator._load_worldbuilding(novel_id)
        
        # 4. 调用 AI 生成完整角色卡
        full_char_data = await bible_generator._generate_full_character_card(
            {
                'name': character.name,
                'role': character.role or '',
                'description': character.description or ''
            },
            existing_worldbuilding,
            []  # TODO: 可以传入其他角色建立关系
        )
        
        # 5. 更新角色字段
        repo = _get_bible_repository()
        
        # 只更新空白的字段，保留用户已填写的内容
        if not character.gender and full_char_data.get('gender'):
            character.gender = full_char_data['gender']
        if not character.age and full_char_data.get('age'):
            character.age = full_char_data['age']
        if not character.identity and full_char_data.get('identity'):
            character.identity = full_char_data['identity']
        if not character.appearance and full_char_data.get('appearance'):
            character.appearance = full_char_data['appearance']
        if not character.personality and full_char_data.get('personality'):
            character.personality = full_char_data['personality']
        if not character.strengths and full_char_data.get('strengths'):
            character.strengths = full_char_data['strengths']
        if not character.weaknesses and full_char_data.get('weaknesses'):
            character.weaknesses = full_char_data['weaknesses']
        if not character.habits and full_char_data.get('habits'):
            character.habits = full_char_data['habits']
        if not character.background and full_char_data.get('background'):
            character.background = full_char_data['background']
        if not character.motivation and full_char_data.get('motivation'):
            character.motivation = full_char_data['motivation']
        if not character.goal and full_char_data.get('goal'):
            character.goal = full_char_data['goal']
        if not character.power_system and full_char_data.get('power_system'):
            character.power_system = full_char_data['power_system']
        if not character.skills and full_char_data.get('skills'):
            character.skills = full_char_data['skills']
        if not character.equipment and full_char_data.get('equipment'):
            character.equipment = full_char_data['equipment']
        if not character.character_arc and full_char_data.get('character_arc'):
            character.character_arc = full_char_data['character_arc']
        if not character.mental_state and full_char_data.get('mental_state'):
            character.mental_state = full_char_data['mental_state']
        if not character.verbal_tic and full_char_data.get('verbal_tic'):
            character.verbal_tic = full_char_data['verbal_tic']
        if not character.idle_behavior and full_char_data.get('idle_behavior'):
            character.idle_behavior = full_char_data['idle_behavior']
        
        # 6. 保存 Bible
        repo.save(bible)
        
        logger.info(f"Completed character card with AI: {character.name} ({character_id})")
        
        return {
            "success": True,
            "character_id": character_id,
            "completed_fields": len([k for k, v in full_char_data.items() if v]),
            "data": full_char_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to complete character card: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete character card: {str(e)}"
        )


@router.get("/novels/{novel_id}/bible/characters/{character_id}/references")
async def check_character_references(
    novel_id: str,
    character_id: str,
    bible_service: BibleService = Depends(get_bible_service)
):
    """检查角色的所有引用
    
    Args:
        novel_id: 小说 ID
        character_id: 角色 ID
        bible_service: Bible 服务
        
    Returns:
        角色的引用信息
    """
    try:
        # 1. 获取 Bible
        bible = bible_service.get_bible_by_novel(novel_id)
        
        if bible is None:
            raise HTTPException(
                status_code=404,
                detail=f"Bible not found for novel: {novel_id}"
            )
        
        # 2. 查找角色
        character = None
        for char in bible.characters:
            if char.id == character_id or char.name == character_id:
                character = char
                break
        
        if character is None:
            raise HTTPException(
                status_code=404,
                detail=f"Character not found: {character_id}"
            )
        
        # 3. 检查章节引用
        from infrastructure.persistence.database.chapter_element_repository import ChapterElementRepository
        from application.paths import get_db_path
        
        db_path = get_db_path()
        chapter_element_repo = ChapterElementRepository(db_path)
        
        # 查询角色在哪些章节出现过
        from domain.structure.chapter_element import ElementType
        import asyncio
        
        chapter_references = await chapter_element_repo.get_by_element(
            ElementType.CHARACTER,
            character.id
        )
        
        # 获取章节详情
        chapters_info = []
        if chapter_references:
            # 去重章节 ID
            chapter_ids = list(set([ref.chapter_id for ref in chapter_references]))
            
            # 获取章节信息
            from infrastructure.persistence.database.sqlite_story_node_repository import SQLiteStoryNodeRepository
            story_node_repo = SQLiteStoryNodeRepository(settings.SQLITE_DB_PATH)
            
            for chapter_id in chapter_ids:
                chapter = await story_node_repo.get_by_id(chapter_id)
                if chapter:
                    # 统计该角色在此章节的出现次数
                    appearances = [ref for ref in chapter_references if ref.chapter_id == chapter_id]
                    chapters_info.append({
                        "chapter_id": chapter_id,
                        "chapter_number": getattr(chapter, 'number', None),
                        "chapter_title": getattr(chapter, 'title', None),
                        "appearance_count": len(appearances),
                        "relation_types": list(set([ref.relation_type.value for ref in appearances]))
                    })
        
        # 4. 检查角色关系（其他角色是否引用此角色）
        relationships = []
        for char in bible.characters:
            if char.id != character.id and hasattr(char, 'relationships') and char.relationships:
                for rel in char.relationships:
                    if isinstance(rel, dict):
                        if rel.get('target_id') == character.id or rel.get('target_name') == character.name:
                            relationships.append({
                                "source_character_id": char.id,
                                "source_character_name": char.name,
                                "relationship": rel
                            })
                    elif hasattr(rel, 'target_id'):
                        if rel.target_id == character.id:
                            relationships.append({
                                "source_character_id": char.id,
                                "source_character_name": char.name,
                                "relationship": str(rel)
                            })
        
        # 5. 检查是否是主角或重要角色
        is_important = character.role in ['主角', '主角/protagonist', 'protagonist']
        
        return {
            "success": True,
            "character": {
                "id": character.id,
                "name": character.name,
                "role": character.role
            },
            "references": {
                "chapter_count": len(chapters_info),
                "total_appearances": len(chapter_references),
                "chapters": sorted(chapters_info, key=lambda x: x.get('chapter_number') or 0),
                "relationship_count": len(relationships),
                "relationships": relationships,
                "is_important_character": is_important
            },
            "can_delete": len(chapter_references) == 0 and len(relationships) == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to check character references: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check character references: {str(e)}"
        )


@router.delete("/novels/{novel_id}/bible/characters/{character_id}")
async def delete_character(
    novel_id: str,
    character_id: str,
    request: Dict[str, Any],
    bible_service: BibleService = Depends(get_bible_service)
):
    """删除角色（带安全检查）
    
    Args:
        novel_id: 小说 ID
        character_id: 角色 ID
        request: 请求数据（包含 force_delete 选项）
        bible_service: Bible 服务
        
    Returns:
        删除结果
    """
    try:
        # 1. 获取 Bible 领域实体
        repo = _get_bible_repository()
        from domain.novel.value_objects.novel_id import NovelId
        bible = repo.get_by_novel_id(NovelId(novel_id))
        
        if bible is None:
            raise HTTPException(
                status_code=404,
                detail=f"Bible not found for novel: {novel_id}"
            )
        
        # 2. 查找角色
        character = None
        character_index = -1
        for i, char in enumerate(bible.characters):
            if char.character_id.value == character_id or char.name == character_id:
                character = char
                character_index = i
                break
        
        if character is None:
            raise HTTPException(
                status_code=404,
                detail=f"Character not found: {character_id}"
            )
        
        # 3. 安全检查
        force_delete = request.get('force_delete', False)
        
        if not force_delete:
            # 检查章节引用
            from infrastructure.persistence.database.chapter_element_repository import ChapterElementRepository
            from application.paths import get_db_path
            from domain.structure.chapter_element import ElementType
            
            db_path = get_db_path()
            chapter_element_repo = ChapterElementRepository(db_path)
            
            chapter_references = await chapter_element_repo.get_by_element(
                ElementType.CHARACTER,
                character.character_id.value
            )
            
            if len(chapter_references) > 0:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "character_has_references",
                        "message": f"角色 '{character.name}' 在 {len(chapter_references)} 个章节元素中被引用，无法删除",
                        "reference_count": len(chapter_references),
                        "suggestion": "请先删除所有章节中的角色引用，或使用 force_delete=true 强制删除"
                    }
                )
            
            # 检查角色关系
            for char in bible.characters:
                if char.character_id.value != character.character_id.value:
                    if hasattr(char, 'relationships') and char.relationships:
                        for rel in char.relationships:
                            if isinstance(rel, dict):
                                if rel.get('target_id') == character.character_id.value:
                                    raise HTTPException(
                                        status_code=400,
                                        detail={
                                            "error": "character_has_relationships",
                                            "message": f"角色 '{char.name}' 与 '{character.name}' 存在关系，无法删除",
                                            "suggestion": "请先删除角色关系，或使用 force_delete=true 强制删除"
                                        }
                                    )
        
        # 4. 删除角色
        deleted_character = bible.characters.pop(character_index)
        
        # 5. 保存 Bible
        repo.save(bible)
        
        logger.info(f"Deleted character: {deleted_character.name} ({character_id})")
        
        return {
            "success": True,
            "message": f"成功删除角色: {deleted_character.name}",
            "deleted_character": {
                "id": deleted_character.character_id.value,
                "name": deleted_character.name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete character: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete character: {str(e)}"
        )


@router.post("/novels/{novel_id}/bible/world-settings", response_model=BibleDTO)
async def add_world_setting(
    novel_id: str,
    request: AddWorldSettingRequest,
    service: BibleService = Depends(get_bible_service)
):
    """添加世界设定到 Bible

    Args:
        novel_id: 小说 ID
        request: 添加世界设定请求
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    try:
        return service.add_world_setting(
            novel_id=novel_id,
            setting_id=request.setting_id,
            name=request.name,
            description=request.description,
            setting_type=request.setting_type
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/novels/{novel_id}/bible/locations", response_model=BibleDTO)
async def add_location(
    novel_id: str,
    request: AddLocationRequest,
    service: BibleService = Depends(get_bible_service)
):
    """添加地点到 Bible

    Args:
        novel_id: 小说 ID
        request: 添加地点请求
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    try:
        return service.add_location(
            novel_id=novel_id,
            location_id=request.location_id,
            name=request.name,
            description=request.description,
            location_type=request.location_type,
            parent_id=request.parent_id,
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/novels/{novel_id}/bible/timeline-notes", response_model=BibleDTO)
async def add_timeline_note(
    novel_id: str,
    request: AddTimelineNoteRequest,
    service: BibleService = Depends(get_bible_service)
):
    """添加时间线笔记到 Bible

    Args:
        novel_id: 小说 ID
        request: 添加时间线笔记请求
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    try:
        return service.add_timeline_note(
            novel_id=novel_id,
            note_id=request.note_id,
            event=request.event,
            time_point=request.time_point,
            description=request.description
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/novels/{novel_id}/bible/style-notes", response_model=BibleDTO)
async def add_style_note(
    novel_id: str,
    request: AddStyleNoteRequest,
    service: BibleService = Depends(get_bible_service)
):
    """添加风格笔记到 Bible

    Args:
        novel_id: 小说 ID
        request: 添加风格笔记请求
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    try:
        return service.add_style_note(
            novel_id=novel_id,
            note_id=request.note_id,
            category=request.category,
            content=request.content
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/novels/{novel_id}/bible", response_model=BibleDTO)
async def bulk_update_bible(
    novel_id: str,
    request: BulkUpdateBibleRequest,
    service: BibleService = Depends(get_bible_service)
):
    """批量更新 Bible 的所有数据

    Args:
        novel_id: 小说 ID
        request: 批量更新请求
        service: Bible 服务

    Returns:
        更新后的 Bible DTO

    Raises:
        HTTPException: 如果 Bible 不存在
    """
    try:
        return service.update_bible(
            novel_id=novel_id,
            characters=request.characters,
            world_settings=request.world_settings,
            locations=request.locations,
            timeline_notes=request.timeline_notes,
            style_notes=request.style_notes
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
