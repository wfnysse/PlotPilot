"""自动 Bible 生成器 - 从小说标题生成完整的人物、地点、风格设定和世界观"""
import logging
import json
import uuid
import re
from typing import Dict, Any, Optional
from datetime import datetime
from domain.ai.services.llm_service import LLMService, GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from application.world.services.bible_service import BibleService
from application.world.services.worldbuilding_service import WorldbuildingService
from application.ai.knowledge_llm_contract import parse_json_from_response
from domain.bible.triple import Triple, SourceType
from infrastructure.persistence.database.triple_repository import TripleRepository
from domain.shared.exceptions import EntityNotFoundError

logger = logging.getLogger(__name__)


# ============================================================================
# Bible 生成进度追踪
# ============================================================================

# 全局进度字典：{novel_id: {"stage": str, "current_step": int, "total_steps": int, "message": str, "progress": float}}
_bible_generation_progress: Dict[str, Dict[str, Any]] = {}


def get_bible_progress(novel_id: str) -> Optional[Dict[str, Any]]:
    """获取指定小说的 Bible 生成进度"""
    return _bible_generation_progress.get(novel_id)


def _update_progress(novel_id: str, stage: str, current_step: int, total_steps: int, message: str):
    """更新 Bible 生成进度
    
    Args:
        novel_id: 小说 ID
        stage: 当前阶段 (worldbuilding / characters / locations / knowledge / done)
        current_step: 当前步骤序号
        total_steps: 总步骤数
        message: 进度描述消息
    """
    progress = (current_step / total_steps) * 100 if total_steps > 0 else 0
    _bible_generation_progress[novel_id] = {
        "novel_id": novel_id,
        "stage": stage,
        "current_step": current_step,
        "total_steps": total_steps,
        "message": message,
        "progress": round(progress, 1),
        "updated_at": datetime.now().isoformat()
    }
    logger.info(f"[进度] {novel_id}: {message} ({progress:.1f}%)")


def _clear_progress(novel_id: str):
    """清除指定小说的进度记录"""
    _bible_generation_progress.pop(novel_id, None)


# ============================================================================
# JSON 输出稳定性增强 - Prompt 常量
# ============================================================================
USER_PROMPT_SUFFIX = """

请按照以下json格式进行输出，可以被Python json.loads函数解析。只给出JSON，不作解释，不作答：
```json
"""


def _infer_character_importance(char_data: Dict[str, Any]) -> str:
    """与前端人物关系图 importance 一致：primary / secondary / minor。"""
    role = str(char_data.get("role") or "").strip()
    desc_head = str(char_data.get("description") or "")[:160]
    blob = f"{role}{desc_head}"
    if "主角" in blob:
        return "primary"
    if any(k in blob for k in ("导师", "师父", "宿敌", "反派", "对手", "核心", "幕后")):
        return "secondary"
    return "minor"


def _map_location_kind(raw_type: str) -> str:
    """与 KnowledgeTriple.location_type 枚举对齐。"""
    t = str(raw_type or "")
    if "城" in t:
        return "city"
    if any(k in t for k in ("区域", "域", "境", "荒", "谷", "原", "山脉")):
        return "region"
    if any(k in t for k in ("建筑", "楼", "殿", "阁", "府", "宫", "塔")):
        return "building"
    if any(k in t for k in ("势力", "宗", "门", "派", "盟", "族")):
        return "faction"
    if any(k in t for k in ("特殊", "秘境", "领域", "遗迹", "墟")):
        return "realm"
    return "region"


def _default_location_importance(_loc_data: Dict[str, Any]) -> str:
    return "normal"


class AutoBibleGenerator:
    """自动 Bible 生成器

    根据小说标题，使用 LLM 生成：
    - 3-5 个主要人物（主角、配角、对手、导师等）
    - 2-3 个重要地点
    - 文风公约
    - 世界观（5维度框架）
    """

    def __init__(self, llm_service: LLMService, bible_service: BibleService, worldbuilding_service: WorldbuildingService = None, triple_repository: TripleRepository = None):
        self.llm_service = llm_service
        self.bible_service = bible_service
        self.worldbuilding_service = worldbuilding_service
        self.triple_repository = triple_repository

    def _ensure_bible_exists(self, novel_id: str) -> None:
        """确保 novel 对应的 Bible 记录存在。"""
        existing_bible = self.bible_service.get_bible_by_novel(novel_id)
        if existing_bible is not None:
            return

        bible_id = f"{novel_id}-bible"
        self.bible_service.create_bible(bible_id, novel_id)
        logger.info("Successfully created Bible %s for novel %s", bible_id, novel_id)

    def _prepare_locations_for_save(self, novel_id: str, locations: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """规范化地点列表，确保父节点优先、缺失父节点降级为根节点。"""
        prepared: list[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        raw_to_final: dict[str, str] = {}

        for idx, loc_data in enumerate(locations or []):
            raw_id = loc_data.get("id")
            normalized_raw_id = (
                str(raw_id).strip()
                if isinstance(raw_id, str) and str(raw_id).strip()
                else ""
            )
            location_id = normalized_raw_id or f"{novel_id}-loc-{idx+1}"
            if location_id in seen_ids:
                logger.info("Location ID %s already exists in generated payload, generating fallback ID", location_id)
                location_id = f"{novel_id}-loc-{idx+1}-{len(seen_ids)}"
            seen_ids.add(location_id)
            if normalized_raw_id and normalized_raw_id not in raw_to_final:
                raw_to_final[normalized_raw_id] = location_id

            prepared.append(
                {
                    "location_id": location_id,
                    "name": loc_data["name"],
                    "description": loc_data["description"],
                    "location_type": loc_data.get("type", "场景"),
                    "connections": loc_data.get("connections", []),
                    "raw_parent_id": loc_data.get("parent_id"),
                }
            )

        valid_ids = {item["location_id"] for item in prepared}
        for item in prepared:
            p_raw = item.pop("raw_parent_id", None)
            parent_id = (
                str(p_raw).strip()
                if isinstance(p_raw, str) and str(p_raw).strip()
                else None
            )
            if parent_id:
                parent_id = raw_to_final.get(parent_id, parent_id)
            if parent_id and parent_id not in valid_ids:
                logger.warning(
                    "Generated location %s references missing parent_id=%s, degrading to root node",
                    item["location_id"],
                    parent_id,
                )
                parent_id = None
            item["parent_id"] = parent_id

        ordered: list[Dict[str, Any]] = []
        remaining = prepared[:]
        saved_ids: set[str] = set()
        while remaining:
            progressed = False
            next_remaining: list[Dict[str, Any]] = []
            for item in remaining:
                parent_id = item["parent_id"]
                if parent_id is None or parent_id in saved_ids:
                    ordered.append(item)
                    saved_ids.add(item["location_id"])
                    progressed = True
                else:
                    next_remaining.append(item)

            if not progressed:
                for item in next_remaining:
                    logger.warning(
                        "Location %s still has unresolved parent %s after ordering, degrading to root node",
                        item["location_id"],
                        item["parent_id"],
                    )
                    item["parent_id"] = None
                    ordered.append(item)
                    saved_ids.add(item["location_id"])
                break

            remaining = next_remaining

        return ordered

    async def generate_and_save(
        self,
        novel_id: str,
        premise: str,
        target_chapters: int,
        stage: str = "all"
    ) -> Dict[str, Any]:
        """生成并保存 Bible（支持分阶段）

        Args:
            novel_id: 小说 ID
            premise: 故事梗概/创意
            target_chapters: 目标章节数
            stage: 生成阶段 (all/worldbuilding/characters/locations)

        Returns:
            生成的 Bible 数据
        """
        logger.info(f"Generating Bible for novel: {premise[:50]}... (stage: {stage})")

        # 初始化进度
        _update_progress(novel_id, "starting", 0, 5, "正在初始化...")

        # 1. 创建空 Bible（如果不存在）
        try:
            self._ensure_bible_exists(novel_id)
            _update_progress(novel_id, "starting", 1, 5, "Bible 记录已创建")
        except Exception as e:
            logger.error(f"Error checking/creating Bible: {e}")
            _update_progress(novel_id, "error", 1, 5, f"初始化失败: {e}")
            raise

        # 2. 根据阶段生成不同内容
        if stage == "all":
            # 一次性生成所有内容（向后兼容）
            _update_progress(novel_id, "worldbuilding", 1, 5, "正在生成世界观和文风...")
            bible_data = await self._generate_bible_data(premise, target_chapters)
            _update_progress(novel_id, "worldbuilding", 2, 5, "世界观生成完毕，正在保存...")
            await self._save_to_bible(novel_id, bible_data)
            if self.worldbuilding_service and "worldbuilding" in bible_data:
                await self._save_worldbuilding(novel_id, bible_data["worldbuilding"])
            _update_progress(novel_id, "done", 5, 5, "Bible 生成完成！")

        elif stage == "worldbuilding":
            self._ensure_bible_exists(novel_id)

            # 只生成世界观和文风
            _update_progress(novel_id, "worldbuilding", 1, 6, "正在初始化...")
            _update_progress(novel_id, "worldbuilding", 2, 6, "正在分析故事创意...")
            _update_progress(novel_id, "worldbuilding", 3, 6, "正在调用大语言模型生成世界观...")
            bible_data = await self._generate_worldbuilding_and_style(premise, target_chapters)
            _update_progress(novel_id, "worldbuilding", 4, 6, "世界观生成完毕，正在解析...")
            logger.info(f"Worldbuilding generated, keys: {bible_data.keys()}")
            logger.info(f"Has worldbuilding key: {'worldbuilding' in bible_data}")
            
            _update_progress(novel_id, "worldbuilding", 5, 6, "正在保存文风公约...")
            # 保存文风
            if "style" in bible_data:
                style_id = f"{novel_id}-style-1"
                try:
                    self.bible_service.add_style_note(
                        novel_id=novel_id,
                        note_id=style_id,
                        category="文风公约",
                        content=bible_data["style"]
                    )
                    logger.info(f"Style note saved: {style_id}")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"Style note {style_id} already exists, skipping")
                    else:
                        logger.error(f"Failed to save style note: {e}")
                        raise
            # 保存世界观
            _update_progress(novel_id, "worldbuilding", 6, 6, "正在保存世界观...")
            if self.worldbuilding_service and "worldbuilding" in bible_data:
                await self._save_worldbuilding(novel_id, bible_data["worldbuilding"])
            _update_progress(novel_id, "done", 6, 6, "世界观生成完成！")

        elif stage == "characters":
            logger.info(f"=== 开始角色生成阶段 ===")
            self._ensure_bible_exists(novel_id)

            _update_progress(novel_id, "characters", 1, 5, "正在加载世界观...")
            existing_worldbuilding = self._load_worldbuilding(novel_id)
            logger.info(f"已加载世界观，keys: {list(existing_worldbuilding.keys())}")
            
            _update_progress(novel_id, "characters", 2, 5, "正在生成角色...")
            logger.info(f"调用 _generate_characters...")
            bible_data = await self._generate_characters(premise, target_chapters, existing_worldbuilding)
            logger.info(f"_generate_characters 返回，bible_data keys: {list(bible_data.keys())}")
            
            if not bible_data.get("characters") or len(bible_data["characters"]) == 0:
                logger.error(f"严重错误：没有生成任何角色！bible_data = {bible_data}")
                _update_progress(novel_id, "error", 2, 5, "角色生成失败：没有返回任何角色")
                raise ValueError("角色生成失败：没有返回任何角色")
            
            _update_progress(novel_id, "characters", 3, 5, "正在保存角色...")
            character_ids = []
            logger.info(f"开始保存 {len(bible_data.get('characters', []))} 个角色...")
            for idx, char_data in enumerate(bible_data.get("characters", [])):
                character_id = f"{novel_id}-char-{idx+1}"
                logger.info(f"正在保存角色 {idx + 1}/{len(bible_data.get('characters', []))}: {char_data.get('name', 'N/A')}")
                try:
                    desc_parts = []
                    if char_data.get("role"):
                        desc_parts.append(char_data["role"])
                    if char_data.get("description"):
                        desc_parts.append(char_data["description"])
                    description = " - ".join(desc_parts) if desc_parts else "角色"
                    
                    card_fields = [
                        'role', 'gender', 'age', 'identity', 'appearance',
                        'personality', 'strengths', 'weaknesses', 'habits',
                        'background', 'motivation', 'goal',
                        'power_system', 'skills', 'equipment',
                        'character_arc', 'mental_state', 'verbal_tic', 'idle_behavior'
                    ]
                    
                    from domain.novel.value_objects.novel_id import NovelId
                    from domain.bible.value_objects.character_id import CharacterId
                    
                    # 预先检查角色是否已存在
                    bible = self.bible_service.bible_repository.get_by_novel_id(NovelId(novel_id))
                    char_exists = False
                    if bible:
                        for char in bible.characters:
                            if char.character_id.value == character_id:
                                char_exists = True
                                logger.info(f"角色 {character_id} 已存在，更新信息")
                                # 更新角色基本信息
                                char.name = char_data["name"]
                                char.description = description
                                char.relationships = char_data.get("relationships", [])
                                # 更新角色卡字段
                                for field in card_fields:
                                    if field in char_data and char_data[field]:
                                        setattr(char, field, char_data[field])
                                break
                    
                    if char_exists:
                        # 角色已存在，保存更新
                        self.bible_service.bible_repository.save(bible)
                    else:
                        # 角色不存在，添加新角色
                        self.bible_service.add_character(
                            novel_id=novel_id,
                            character_id=character_id,
                            name=char_data["name"],
                            description=description,
                            relationships=char_data.get("relationships", [])
                        )
                        # 保存角色卡字段
                        if any(key in char_data for key in card_fields):
                            logger.info(f"角色 {char_data.get('name')} 有额外字段，保存完整角色卡")
                            bible = self.bible_service.bible_repository.get_by_novel_id(NovelId(novel_id))
                            if bible:
                                for char in bible.characters:
                                    if char.character_id.value == character_id:
                                        for field in card_fields:
                                            if field in char_data and char_data[field]:
                                                setattr(char, field, char_data[field])
                                        break
                                self.bible_service.bible_repository.save(bible)
                    
                    character_ids.append((character_id, char_data))
                    logger.info(f"角色保存成功: {character_id} - {char_data['name']}")
                except Exception as e:
                    logger.error(f"保存角色失败: {e}", exc_info=True)
                    raise
            
            _update_progress(novel_id, "characters", 4, 5, "正在生成角色关系...")
            if self.triple_repository:
                await self._generate_character_triples(novel_id, character_ids)
            
            _update_progress(novel_id, "done", 5, 5, "角色生成完成！")
            logger.info(f"=== 角色生成完成，共保存 {len(character_ids)} 个角色 ===")

        elif stage == "locations":
            self._ensure_bible_exists(novel_id)

            # 基于已有世界观和人物生成地点
            _update_progress(novel_id, "locations", 1, 4, "正在加载世界观和角色...")
            existing_worldbuilding = self._load_worldbuilding(novel_id)
            existing_characters = self._load_characters(novel_id)
            
            _update_progress(novel_id, "locations", 2, 4, "正在生成地点...")
            bible_data = await self._generate_locations(premise, target_chapters, existing_worldbuilding, existing_characters)
            # 保存地点
            _update_progress(novel_id, "locations", 3, 4, "正在保存地点...")
            location_ids = []
            for loc_data in self._prepare_locations_for_save(novel_id, bible_data.get("locations", [])):
                try:
                    self.bible_service.add_location(
                        novel_id=novel_id,
                        location_id=loc_data["location_id"],
                        name=loc_data["name"],
                        description=loc_data["description"],
                        location_type=loc_data["location_type"],
                        connections=loc_data["connections"],
                        parent_id=loc_data["parent_id"],
                    )
                    location_ids.append((loc_data["location_id"], loc_data))
                    logger.info(f"Location saved: {loc_data['location_id']}")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"Location {loc_data['location_id']} already exists, skipping")
                    else:
                        logger.error(f"Failed to save location: {e}")
                        raise

            # 从地点连接生成三元组
            if self.triple_repository:
                _update_progress(novel_id, "locations", 4, 4, "正在生成知识三元组...")
                await self._generate_location_triples(novel_id, location_ids)
            
            _update_progress(novel_id, "done", 4, 4, "地点生成完成！")

        else:
            raise ValueError(f"Unknown stage: {stage}")

        logger.info(f"Bible generation completed for {novel_id} (stage: {stage})")
        return bible_data

    async def confirm_and_save_characters(
        self,
        novel_id: str,
        characters: list[Dict[str, Any]],
        generate_full_card: bool = True
    ) -> Dict[str, Any]:
        """确认并保存角色，可选择生成完整角色卡
        
        Args:
            novel_id: 小说 ID
            characters: 用户确认的角色列表
            generate_full_card: 是否生成完整角色卡（默认 True）
            
        Returns:
            保存结果
        """
        logger.info(f"Confirming and saving {len(characters)} characters for {novel_id}")
        
        self._ensure_bible_exists(novel_id)
        
        # 加载世界观（用于生成角色卡）
        existing_worldbuilding = self._load_worldbuilding(novel_id)
        
        character_ids = []
        used_char_ids = set()
        
        for idx, char_data in enumerate(characters):
            character_id = f"{novel_id}-char-{idx+1}"
            
            # 检查并处理重复ID
            if character_id in used_char_ids:
                logger.info(f"Character ID {character_id} already exists, generating new ID")
                character_id = f"{novel_id}-char-{idx+1}-{len(used_char_ids)}"
            
            used_char_ids.add(character_id)
            
            try:
                # 【新增】如果需要生成完整角色卡
                if generate_full_card:
                    # 调用 AI 生成完整角色卡
                    full_char_data = await self._generate_full_character_card(
                        char_data, 
                        existing_worldbuilding,
                        characters  # 传入所有角色以便建立关系
                    )
                    
                    # 合并数据
                    char_data.update(full_char_data)
                
                # 保存角色
                self.bible_service.add_character(
                    novel_id=novel_id,
                    character_id=character_id,
                    name=char_data["name"],
                    description=f"{char_data.get('role', '')} - {char_data.get('description', '')}",
                    relationships=char_data.get("relationships", [])
                )
                
                # 【新增】如果有角色卡扩展字段，更新到数据库
                if any(key in char_data for key in [
                    'role', 'gender', 'age', 'identity', 'appearance',
                    'personality', 'strengths', 'weaknesses', 'habits',
                    'background', 'motivation', 'goal',
                    'power_system', 'skills', 'equipment',
                    'character_arc', 'mental_state', 'verbal_tic', 'idle_behavior'
                ]):
                    from infrastructure.persistence.database.sqlite_bible_repository import SqliteBibleRepository
                    from infrastructure.persistence.database.connection import DatabaseConnection
                    from application.paths import get_db_path
                    
                    db_path = get_db_path()
                    db_conn = DatabaseConnection(db_path)
                    repo = SqliteBibleRepository(db_conn)
                    bible = self.bible_service.get_bible_by_novel(novel_id)
                    
                    # 查找刚添加的角色并更新
                    for char in bible.characters:
                        if char.character_id.value == character_id:
                            # 更新角色卡字段
                            if 'role' in char_data:
                                char.role = char_data['role']
                            if 'gender' in char_data:
                                char.gender = char_data['gender']
                            if 'age' in char_data:
                                char.age = char_data['age']
                            if 'identity' in char_data:
                                char.identity = char_data['identity']
                            if 'appearance' in char_data:
                                char.appearance = char_data['appearance']
                            if 'personality' in char_data:
                                char.personality = char_data['personality']
                            if 'strengths' in char_data:
                                char.strengths = char_data['strengths']
                            if 'weaknesses' in char_data:
                                char.weaknesses = char_data['weaknesses']
                            if 'habits' in char_data:
                                char.habits = char_data['habits']
                            if 'background' in char_data:
                                char.background = char_data['background']
                            if 'motivation' in char_data:
                                char.motivation = char_data['motivation']
                            if 'goal' in char_data:
                                char.goal = char_data['goal']
                            if 'power_system' in char_data:
                                char.power_system = char_data['power_system']
                            if 'skills' in char_data:
                                char.skills = char_data['skills']
                            if 'equipment' in char_data:
                                char.equipment = char_data['equipment']
                            if 'character_arc' in char_data:
                                char.character_arc = char_data['character_arc']
                            if 'mental_state' in char_data:
                                char.mental_state = char_data['mental_state']
                            if 'verbal_tic' in char_data:
                                char.verbal_tic = char_data['verbal_tic']
                            if 'idle_behavior' in char_data:
                                char.idle_behavior = char_data['idle_behavior']
                            break
                    
                    # 保存 Bible
                    repo.save(bible)
                
                character_ids.append((character_id, char_data))
                logger.info(f"Character saved with card: {character_id} - {char_data['name']}")
                
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Character {character_id} already exists, skipping")
                else:
                    logger.error(f"Failed to save character: {e}")
                    raise
        
        # 从人物关系生成三元组
        if self.triple_repository:
            await self._generate_character_triples(novel_id, character_ids)
        
        logger.info(f"All characters confirmed and saved for {novel_id}")
        return {
            "success": True,
            "characters_saved": len(character_ids),
            "character_ids": [cid for cid, _ in character_ids]
        }
    
    async def _generate_full_character_card(
        self,
        char_data: Dict[str, Any],
        worldbuilding: Dict[str, Any],
        all_characters: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用 AI 生成完整的角色卡
        
        Args:
            char_data: 基础角色数据（name, role, description）
            worldbuilding: 世界观数据
            all_characters: 所有角色列表（用于建立关系）
            
        Returns:
            完整的角色卡数据
        """
        wb_summary = self._summarize_worldbuilding(worldbuilding)
        
        system_prompt = """你是资深网文策划编辑。基于已有世界观和角色基本信息，生成完整的角色卡。

**重要：所有字段必须是单行文本，用逗号或分号分隔不同要点。**

要求：
1. 角色要符合世界观设定
2. 性格要有层次，不能过于单一
3. 背景故事要与世界观和其他角色呼应
4. 能力体系要符合世界观的力量体系
5. 角色发展轨迹要合理
6. 精神状态要符合角色当前处境
7. 口头禅要符合角色性格和身份
8. 闲时行为要体现角色个性

JSON 格式：
{
  "gender": "男/女",
  "age": "年龄",
  "identity": "身份/职业",
  "appearance": "外貌特征，单行文本",
  "personality": "性格关键词，用逗号分隔",
  "strengths": "优点，用逗号分隔",
  "weaknesses": "缺点，用逗号分隔",
  "habits": "行为习惯，用逗号分隔",
  "background": "背景故事，单行文本",
  "motivation": "动机",
  "goal": "目标",
  "power_system": "力量体系/能力",
  "skills": "技能，用逗号分隔",
  "equipment": "装备/道具，用逗号分隔",
  "character_arc": "角色弧光/成长路线",
  "mental_state": "NORMAL(正常)/ANXIOUS(焦虑)/DEPRESSED(沮丧)/EXCITED(兴奋)/ANGRY(愤怒)/FEARFUL(恐惧)",
  "verbal_tic": "口头禅/标志性台词，单行文本",
  "idle_behavior": "空闲时的习惯性行为和动作，单行文本"
}"""
        
        other_chars = ", ".join([c["name"] for c in all_characters if c["name"] != char_data["name"]])
        
        user_prompt = f"""世界观：
{wb_summary}

角色基本信息：
- 姓名：{char_data['name']}
- 定位：{char_data.get('role', '')}
- 描述：{char_data.get('description', '')}
- 其他角色：{other_chars}

请基于这个世界观和角色基本信息，生成完整的角色卡。

请按照以下json格式进行输出，可以被Python json.loads函数解析。只给出JSON，不作解释，不作答：
```json
{{
  "gender": "",
  "age": "",
  "identity": "",
  "appearance": "",
  "personality": "",
  "strengths": "",
  "weaknesses": "",
  "habits": "",
  "background": "",
  "motivation": "",
  "goal": "",
  "power_system": "",
  "skills": "",
  "equipment": "",
  "character_arc": "",
  "mental_state": "NORMAL",
  "verbal_tic": "",
  "idle_behavior": ""
}}
```"""
        
        try:
            result = await self._call_llm_and_parse_with_retry(system_prompt, user_prompt)
            if result:
                logger.info(f"Generated full character card for {char_data['name']}")
                return result
        except Exception as e:
            logger.warning(f"Failed to generate full character card for {char_data['name']}: {e}")
        
        # 如果生成失败，返回空值
        return {
            "gender": "",
            "age": "",
            "identity": "",
            "appearance": "",
            "personality": "",
            "strengths": "",
            "weaknesses": "",
            "habits": "",
            "background": "",
            "motivation": "",
            "goal": "",
            "power_system": "",
            "skills": "",
            "equipment": "",
            "character_arc": "",
            "mental_state": "NORMAL",
            "verbal_tic": "",
            "idle_behavior": ""
        }

    async def _generate_bible_data(self, premise: str, target_chapters: int) -> Dict[str, Any]:
        """使用 LLM 生成 Bible 数据和世界观"""
        import time
        import random
        random_seed = int(time.time() * 1000) % 100000
        random_surnames = random.sample(["顾", "晏", "陆", "傅", "霍", "沈", "谢", "裴", "萧", "楚", "卫", "温", "江", "秦", "白", "容", "贺", "季", "程", "叶"], 5)

        system_prompt = f"""你是资深网文策划编辑。根据用户提供的故事创意/梗概，生成完整的人物、世界设定和世界观。

**重要：description 字段必须是单行文本，不能有换行符。**

**命名随机性要求（随机种子：{random_seed}）**：
- 必须使用以下姓氏中的至少2个：{', '.join(random_surnames)}
- 每个角色的姓氏必须不同
- 名字必须原创，禁止使用"林渊"、"叶凡"、"苏铭"等高频模板名

要求：
1. 深入理解故事梗概，提取核心冲突、主题、世界观
2. 至少 3-5 个主要人物（主角、配角、对手、导师等），确保人物之间有冲突和互动
3. **每个人物必须生成完整的角色卡（所有字段都要填写）**：
   - 基本信息：gender(男/女), age(年龄), identity(身份/职业), appearance(外貌特征)
   - 性格特征：personality(性格关键词), strengths(优点), weaknesses(缺点), habits(行为习惯)
   - 背景故事：background(背景故事), motivation(动机), goal(目标)
   - 能力体系：power_system(力量体系), skills(技能), equipment(装备/道具)
   - 发展轨迹：character_arc(角色弧光/成长路线)
   - 声线锚点：mental_state(NORMAL/ANXIOUS/DEPRESSED/EXCITED/ANGRY/FEARFUL), verbal_tic(口头禅), idle_behavior(闲时行为)
4. 至少 2-3 个重要地点，符合故事背景；地点须含稳定 `id`，若有层级则填 `parent_id` 指向父地点的 `id`（根为 null）
5. 明确的文风公约（叙事视角、人称、基调、节奏）
6. 完整的世界观（5维度框架）：核心法则、地理生态、社会结构、历史文化、沉浸感细节
7. 人物和地点要符合故事类型（现代都市/古代/玄幻/科幻等）
8. **所有 description 字段必须是单行文本，用逗号或分号分隔不同要点，不要使用换行符**
9. **强制命名规范**：
   - **每次生成必须产生全新的名字，与上一次生成完全不同！**
   - **名字必须易读易记，禁止使用生僻字！**（如："龘、靐、、齾、"等）
   - 姓氏可以常见，但名字组合必须新颖有辨识度
   - 避免连续多次生成相同的名字（如：林渊、叶凡、苏铭等高频名虽然可以接受，但不要每次都抽到）
   - 禁止在同一故事中使用重复的姓氏！每个角色姓氏必须不同！
   - 玄幻/仙侠：名字可带有古风或仙气感（如：顾清寒、晏无师、陆沉、傅九渊、霍惊澜）
   - 都市/现代：名字要符合现代审美但不落俗套（如：顾星辞、晏清欢、陆时深、傅景行、霍明渊）
   - 科幻/末世：名字可带有未来感或冷峻感（如：顾渊、晏星野、陆沉、傅光年、霍明彻）
   - 禁止直接使用现实地名！请使用网文常用的架空代称。
   - 城市示例：魔都(上海)、燕京(北京)、鹏城(深圳)、羊城(广州)
   - 国家示例：华夏(中国)、樱花国(日本)、美丽国(美国)、高丽(韩国)
   - 目标：让读者能对应现实，但保持故事的架空感。
10. **所有字符字段必须是单行文本，用逗号或分号分隔不同要点**

JSON 格式（不要有其他文字）：
{
  "characters": [
    {
      "name": "人物名",
      "role": "主角/配角/对手/导师",
      "description": "性格、背景、目标、特点，所有内容在一行内，用逗号分隔",
      "gender": "男/女",
      "age": "年龄描述",
      "identity": "身份/职业",
      "appearance": "外貌特征，单行文本",
      "personality": "性格关键词，用逗号分隔",
      "strengths": "优点，用逗号分隔",
      "weaknesses": "缺点，用逗号分隔",
      "habits": "行为习惯，用逗号分隔",
      "background": "背景故事，单行文本",
      "motivation": "动机",
      "goal": "目标",
      "power_system": "力量体系/能力",
      "skills": "技能，用逗号分隔",
      "equipment": "装备/道具，用逗号分隔",
      "character_arc": "角色弧光/成长路线",
      "mental_state": "NORMAL",
      "verbal_tic": "口头禅/标志性台词",
      "idle_behavior": "空闲时的习惯性行为"
    }
  ],
  "locations": [
    {
      "id": "稳定id如 loc-continent-1",
      "name": "地点名",
      "type": "城市/建筑/区域",
      "description": "地点描述，单行文本",
      "parent_id": null
    }
  ],
  "style": "第三人称有限视角，以XX视角为主。基调XX，节奏XX。避免XX。营造XX氛围。",
  "worldbuilding": {
    "core_rules": {
      "power_system": "力量体系/科技树的描述",
      "physics_rules": "物理规律的特殊之处",
      "magic_tech": "魔法或科技的运作机制"
    },
    "geography": {
      "terrain": "地形特征",
      "climate": "气候特点",
      "resources": "资源分布",
      "ecology": "生态系统"
    },
    "society": {
      "politics": "政治体制",
      "economy": "经济模式",
      "class_system": "阶级系统",
      "naming_rules": "禁止使用现实地名，必须使用架空名称"
    },
    "culture": {
      "history": "关键历史事件",
      "religion": "宗教信仰",
      "taboos": "文化禁忌"
    },
    "daily_life": {
      "food_clothing": "衣食住行",
      "language_slang": "俚语与口音",
      "entertainment": "娱乐方式"
    }
  }
}"""

        user_prompt = f"""故事创意：{premise}

目标章节数：{target_chapters}章

请根据这个故事创意，生成完整的人物、世界设定和世界观。注意：
1. 从故事创意中提取关键信息（主角身份、核心能力、故事背景、主要冲突）
2. 人物要有层次，不能只有主角，要有配角、对手、导师等
3. **每个角色必须生成完整的角色卡，所有字段都要填写（包括声线锚点：mental_state、verbal_tic、idle_behavior）**
4. 要有明确的冲突和对立面
5. 世界观要清晰，地点要符合故事类型
6. 文风公约要具体，明确叙事视角、基调、节奏
7. 世界观5个维度都要填写，符合故事类型和背景
8. 适合网文读者，有代入感
9. **所有字符字段必须是单行文本，用逗号或分号分隔**

请按照以下json格式进行输出，可以被Python json.loads函数解析。只给出JSON，不作解释，不作答：
```json
{{
  "characters": [
    {{
      "name": "",
      "role": "",
      "description": "",
      "gender": "",
      "age": "",
      "identity": "",
      "appearance": "",
      "personality": "",
      "strengths": "",
      "weaknesses": "",
      "habits": "",
      "background": "",
      "motivation": "",
      "goal": "",
      "power_system": "",
      "skills": "",
      "equipment": "",
      "character_arc": "",
      "mental_state": "NORMAL",
      "verbal_tic": "",
      "idle_behavior": ""
    }}
  ],
  "locations": [],
  "style": "",
  "worldbuilding": {{}}
}}
```"""

        bible_data = await self._call_llm_and_parse_with_retry(system_prompt, user_prompt)
        if bible_data:
            return bible_data

        logger.error("Failed to generate Bible data, falling back to default structure")
        return {
                "characters": [
                    {
                        "name": "主角",
                        "role": "主角",
                        "description": "待补充",
                        "gender": "",
                        "age": "",
                        "identity": "",
                        "appearance": "",
                        "personality": "",
                        "strengths": "",
                        "weaknesses": "",
                        "habits": "",
                        "background": "",
                        "motivation": "",
                        "goal": "",
                        "power_system": "",
                        "skills": "",
                        "equipment": "",
                        "character_arc": "",
                        "mental_state": "NORMAL",
                        "verbal_tic": "",
                        "idle_behavior": ""
                    }
                ],
                "locations": [
                    {
                        "id": "loc-default-1",
                        "name": "主要场景",
                        "type": "城市",
                        "description": "待补充",
                        "parent_id": None,
                    }
                ],
                "style": "第三人称有限视角，轻松幽默"
            }

    async def _save_to_bible(self, novel_id: str, bible_data: Dict[str, Any]) -> None:
        """保存到 Bible"""

        # 先确保 Bible 记录存在
        try:
            self._ensure_bible_exists(novel_id)
        except Exception as e:
            logger.error(f"Failed to ensure Bible exists: {e}")
            return

        # 添加人物（包含完整的角色卡信息）
        used_character_ids = set()  # 用于跟踪已使用的人物ID
        for idx, char_data in enumerate(bible_data.get("characters", [])):
            character_id = f"{novel_id}-char-{idx+1}"
            
            # 检查并处理重复ID
            if character_id in used_character_ids:
                logger.info(f"Character ID {character_id} already exists, generating new ID")
                character_id = f"{novel_id}-char-{idx+1}-{len(used_character_ids)}"
            
            used_character_ids.add(character_id)
            try:
                # 直接使用 repository 添加包含完整信息的角色
                from domain.bible.entities.character import Character
                from domain.bible.value_objects.character_id import CharacterId
                from domain.novel.value_objects.novel_id import NovelId
                
                bible = self.bible_repository.get_by_novel_id(NovelId(novel_id))
                if bible is None:
                    logger.error(f"Bible not found for novel {novel_id}")
                    continue
                
                # 创建包含完整角色卡信息的 Character 实体
                character = Character(
                    id=CharacterId(character_id),
                    name=char_data.get("name", ""),
                    description=f"{char_data.get('role', '')} - {char_data.get('description', '')}",
                    relationships=[],
                    # 基本信息
                    role=char_data.get("role", ""),
                    gender=char_data.get("gender", ""),
                    age=char_data.get("age", ""),
                    identity=char_data.get("identity", ""),
                    appearance=char_data.get("appearance", ""),
                    # 性格特征
                    personality=char_data.get("personality", ""),
                    strengths=char_data.get("strengths", ""),
                    weaknesses=char_data.get("weaknesses", ""),
                    habits=char_data.get("habits", ""),
                    # 背景故事
                    background=char_data.get("background", ""),
                    motivation=char_data.get("motivation", ""),
                    goal=char_data.get("goal", ""),
                    # 能力体系
                    power_system=char_data.get("power_system", ""),
                    skills=char_data.get("skills", ""),
                    equipment=char_data.get("equipment", ""),
                    # 发展轨迹
                    character_arc=char_data.get("character_arc", ""),
                    # 声线锚点
                    mental_state=char_data.get("mental_state", "NORMAL"),
                    verbal_tic=char_data.get("verbal_tic", ""),
                    idle_behavior=char_data.get("idle_behavior", ""),
                )
                
                bible.add_character(character)
                self.bible_repository.save(bible)
                logger.info(f"Character saved with full card: {character_id} ({char_data['name']})")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Character {character_id} already exists, skipping")
                else:
                    logger.error(f"Failed to save character: {e}")
                    import traceback
                    traceback.print_exc()
                    raise

        # 添加地点
        for loc_data in self._prepare_locations_for_save(novel_id, bible_data.get("locations", [])):
            try:
                self.bible_service.add_location(
                    novel_id=novel_id,
                    location_id=loc_data["location_id"],
                    name=loc_data["name"],
                    description=loc_data["description"],
                    location_type=loc_data["location_type"],
                    parent_id=loc_data["parent_id"],
                )
                logger.info(f"Location saved: {loc_data['location_id']}")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Location {loc_data['location_id']} already exists, skipping")
                else:
                    logger.error(f"Failed to save location: {e}")
                    raise

        # 添加风格笔记
        style = bible_data.get("style", "")
        if style:
            style_id = f"{novel_id}-style-1"
            try:
                self.bible_service.add_style_note(
                    novel_id=novel_id,
                    note_id=style_id,
                    category="文风公约",
                    content=style
                )
                logger.info(f"Style note saved: {style_id}")
            except Exception as e:
                # 如果已存在则更新
                if "already exists" in str(e):
                    logger.info(f"Style note {style_id} already exists, skipping")
                else:
                    logger.error(f"Failed to save style note: {e}")
                    raise

    async def _save_worldbuilding(self, novel_id: str, worldbuilding_data: Dict[str, Any]) -> None:
        """保存世界观到数据库（同时保存到Worldbuilding表和Bible的world_settings）"""
        logger.info(f"Saving worldbuilding for {novel_id}")

        # 1. 保存到Worldbuilding表（用于后续生成人物和地点时读取）
        if self.worldbuilding_service:
            try:
                self.worldbuilding_service.update_worldbuilding(
                    novel_id=novel_id,
                    core_rules=worldbuilding_data.get("core_rules"),
                    geography=worldbuilding_data.get("geography"),
                    society=worldbuilding_data.get("society"),
                    culture=worldbuilding_data.get("culture"),
                    daily_life=worldbuilding_data.get("daily_life")
                )
                logger.info("Worldbuilding saved to Worldbuilding table")
            except Exception as e:
                logger.error(f"Failed to save worldbuilding: {e}")

        # 2. 同时保存到Bible的world_settings（用于前端显示）
        try:
            logger.info("Saving worldbuilding to Bible.world_settings")
            bible = self.bible_service.get_bible_by_novel(novel_id)
            if not bible:
                bible_id = f"{novel_id}-bible"
                self.bible_service.create_bible(bible_id, novel_id)

            # 将5维度数据转换为world_setting条目
            # WorldSetting的type只能是'rule', 'location', 'item'，所以统一使用'rule'
            import uuid
            for dimension_name, dimension_data in worldbuilding_data.items():
                if isinstance(dimension_data, dict):
                    for key, value in dimension_data.items():
                        setting_id = f"{novel_id}-ws-{uuid.uuid4().hex[:8]}"
                        self.bible_service.add_world_setting(
                            novel_id=novel_id,
                            setting_id=setting_id,
                            name=f"{dimension_name}.{key}",
                            description=value,
                            setting_type="rule"  # 统一使用'rule'类型
                        )
            logger.info("Worldbuilding saved to Bible.world_settings successfully")
        except Exception as e:
            logger.error(f"Failed to save to Bible.world_settings: {e}")

    def _load_worldbuilding(self, novel_id: str) -> Dict[str, Any]:
        """加载已有世界观"""
        if not self.worldbuilding_service:
            return {}
        try:
            wb = self.worldbuilding_service.get_worldbuilding(novel_id)
            return {
                "core_rules": wb.core_rules,
                "geography": wb.geography,
                "society": wb.society,
                "culture": wb.culture,
                "daily_life": wb.daily_life
            }
        except (AttributeError, TypeError, KeyError, EntityNotFoundError):
            return {}

    def _load_characters(self, novel_id: str) -> list:
        """加载已有人物"""
        try:
            bible = self.bible_service.get_bible(novel_id)
            return [{"name": c.name, "description": c.description} for c in bible.characters]
        except (AttributeError, TypeError, EntityNotFoundError):
            return []

    async def _generate_worldbuilding_and_style(self, premise: str, target_chapters: int, existing_wb: Dict[str, Any] = None) -> Dict[str, Any]:
        """只生成世界观和文风"""
        naming_rules = ""
        if existing_wb and existing_wb.get("society", {}).get("naming_rules"):
            naming_rules = f"\n★ 强制命名规范：{existing_wb['society']['naming_rules']}"

        system_prompt = f"""你是资深网文策划编辑。根据故事创意生成世界观和文风公约。

要求：
1. 完整的世界观（5维度框架）：核心法则、地理生态、社会结构、历史文化、沉浸感细节
2. 明确的文风公约（叙事视角、人称、基调、节奏）
3. 符合故事类型（现代都市/古代/玄幻/科幻等）
4. **严格遵守命名规范**：禁止直接使用现实地名！请使用网文常用的架空代称（如：魔都、燕京、华夏、樱花国）。{naming_rules}

JSON 格式：
{{
  "style": "第三人称有限视角，以XX视角为主。基调XX，节奏XX。避免XX。营造XX氛围。",
  "worldbuilding": {{
    "core_rules": {{
      "power_system": "力量体系/科技树的描述",
      "physics_rules": "物理规律的特殊之处",
      "magic_tech": "魔法或科技的运作机制"
    }},
    "geography": {{
      "terrain": "地形特征",
      "climate": "气候特点",
      "resources": "资源分布",
      "ecology": "生态系统"
    }},
    "society": {{
      "politics": "政治体制",
      "economy": "经济模式",
      "class_system": "阶级系统",
      "naming_rules": "{naming_rules.strip()}"
    }},
    "culture": {{
      "history": "关键历史事件",
      "religion": "宗教信仰",
      "taboos": "文化禁忌"
    }},
    "daily_life": {{
      "food_clothing": "衣食住行",
      "language_slang": "俚语与口音",
      "entertainment": "娱乐方式"
    }}
  }}
}}"""

        user_prompt = f"""故事创意：{premise}

目标章节数：{target_chapters}章

请生成世界观和文风公约。{naming_rules}

请按照以下json格式进行输出，可以被Python json.loads函数解析。只给出JSON，不作解释，不作答：
```json
{{
  "style": "",
  "worldbuilding": {{}}
}}
```"""

        return await self._call_llm_and_parse_with_retry(system_prompt, user_prompt)

    async def _generate_characters(self, premise: str, target_chapters: int, worldbuilding: Dict[str, Any]) -> Dict[str, Any]:
        """基于世界观生成人物（仅包含基础信息，速度更快）"""
        logger.info(f"=== 开始生成角色 ===")
        logger.info(f"Premise 长度: {len(premise)} chars")
        logger.info(f"Target chapters: {target_chapters}")
        logger.info(f"Worldbuilding keys: {list(worldbuilding.keys()) if worldbuilding else []}")
        
        import time
        import random
        wb_summary = self._summarize_worldbuilding(worldbuilding)
        logger.info(f"世界观摘要长度: {len(wb_summary)} chars")

        random_seed = int(time.time() * 1000) % 100000
        
        # 热门常用姓氏（主角优先使用）
        popular_surnames = ["李", "王", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "罗", "郑", "梁", "宋", "谢", "唐", "韩", "冯", "于", "董", "萧", "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕", "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎", "余", "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜", "范", "方", "石", "姚", "谭", "廖", "邹", "熊", "金", "陆", "郝", "孔", "白", "崔", "康", "毛", "邱", "秦", "江", "史", "顾", "侯", "邵", "孟", "龙", "万", "段", "雷", "钱", "汤", "尹", "黎", "易", "常", "武", "乔", "贺", "赖", "龚", "文"]
        
        # 网文风格姓氏（配角/反派使用）
        webnovel_surnames = ["顾", "晏", "陆", "傅", "霍", "沈", "谢", "裴", "萧", "楚", "卫", "温", "江", "秦", "白", "容", "贺", "季", "程", "叶"]
        
        # 随机选择姓氏
        selected_popular = random.sample(popular_surnames, 3)
        selected_webnovel = random.sample(webnovel_surnames, 2)
        random_surnames = selected_popular + selected_webnovel
        random.shuffle(random_surnames)
        
        logger.info(f"随机种子: {random_seed}, 随机姓氏: {random_surnames}")

        system_prompt = f"""你是资深网文策划编辑。基于已有世界观生成主要人物及其基础信息。

**重要规则：**
1. description 字段必须是单行文本，用逗号分隔多个要点
2. 所有文本字段都要简洁明了，避免过长
3. 确保人物之间有冲突和互动
4. **命名要求（随机种子：{random_seed}）**：
   - 必须使用以下姓氏中的至少2个：{', '.join(random_surnames)}
   - 每个角色的姓氏必须不同
   - **主角必须优先使用热门常用姓氏（李、王、张、刘、陈等）**
   - **姓名必须符合网文风格，好听、有辨识度、易于记忆**
   - 避免使用"林渊"、"叶凡"、"苏铭"等过于高频的模板名
   - 名字要有辨识度，但也要符合中文网文读者的审美习惯

**网文风格姓名参考：**
- 男主：顾晏、陆沉、傅景深、霍庭琛、沈砚、谢辞、裴听颂、萧策、楚惊尘、卫昭、温时衍、江亦淮、秦墨、白景行、容珩、贺楼、季临、程妄、叶澜
- 女主：顾晚、陆知夏、傅云舒、霍轻瑶、沈若微、谢惜、裴初雪、萧灵、楚汐月、卫清歌、温念、江晚、秦月、白芷、容音、贺晚、季明珠、程雨、叶清辞
- 反派：顾墨染、陆阎、傅枭、霍天、沈惊、谢渊、裴夜、萧灭、楚狱、卫冥、温蚀、江朽、秦逆、白夜、容毁、贺屠、季枯、程烬、叶亡

**必须生成的字段：**
- name: 角色姓名
- role: 角色定位（主角/配角/反派/导师/路人）
- description: 简要描述（单行，100字以内）
- gender: 性别（男/女/其他）
- age: 年龄（如：25岁、青年、中年）
- identity: 身份职业（如：学生、CEO、修仙者）
- appearance: 外貌特征（50字以内）
- personality: 性格特点（30字以内）

JSON 格式示例：
{{
  "characters": [
    {{
      "name": "角色姓名",
      "role": "主角",
      "description": "现代程序员穿越到修仙世界，用工程思维破解修炼难题",
      "gender": "男",
      "age": "25岁",
      "identity": "穿越者、程序员、筑基期修士",
      "appearance": "黑发黑眸，身材瘦削，眼神锐利，常穿灰色道袍",
      "personality": "理性冷静、逻辑缜密、不善言辞、执着求知",
      "relationships": [
        {{
          "target": "另一角色姓名",
          "relation": "师徒",
          "description": "关系描述"
        }}
      ]
    }}
  ]
}}"""

        user_prompt = f"""故事创意：{premise}

已有世界观：
{wb_summary}

请基于这个世界观生成 3-5 个主要人物，每个人物只需要基础信息。

要求：
1. 至少包含：主角、配角、反派/对手
2. 角色之间要有明确的关系和冲突
3. 内容要符合世界观设定
4. 描述要简洁精炼

请按照以下json格式进行输出，可以被Python json.loads函数解析。只给出JSON，不作解释，不作答：
```json
{{
  "characters": []
}}
```"""

        logger.info(f"System prompt 长度: {len(system_prompt)} chars")
        logger.info(f"User prompt 长度: {len(user_prompt)} chars")
        
        result = await self._call_llm_and_parse_with_retry(system_prompt, user_prompt, max_tokens=4000)
        
        logger.info(f"=== 角色生成结果:")
        logger.info(f"返回结果类型: {type(result)}")
        logger.info(f"返回结果 keys: {list(result.keys())}")
        if "characters" in result:
            logger.info(f"生成的角色数量: {len(result['characters'])}")
            for idx, char in enumerate(result['characters']):
                logger.info(f"角色 {idx + 1}: {char.get('name', 'N/A')} - {char.get('role', 'N/A')}")
        else:
            logger.warning(f"返回结果中没有 'characters' 字段！")
        
        return result

    async def _generate_locations(self, premise: str, target_chapters: int, worldbuilding: Dict[str, Any], characters: list) -> Dict[str, Any]:
        """基于世界观和人物生成地点"""
        wb_summary = self._summarize_worldbuilding(worldbuilding)
        char_summary = "\n".join([f"- {c['name']}: {c['description'][:50]}..." for c in characters])
        
        naming_rules = ""
        if worldbuilding and worldbuilding.get("society", {}).get("naming_rules"):
            naming_rules = f"\n★ 强制命名规范：{worldbuilding['society']['naming_rules']}"

        system_prompt = f"""你是资深网文策划编辑。基于已有世界观和人物生成完整地图。

要求：
1. 至少 5-10 个重要地点，构成完整地图
2. 地点要符合世界观设定
3. 考虑人物的活动范围和故事需要
4. 包含不同类型：城市、建筑、区域、特殊场所等
5. 空间层级用 `parent_id` 表达（子地点 id 指向父地点 id）；非父子关系用 `connections`（不要用 relation=位于）
6. **严格遵守命名规范**：禁止直接使用现实地名！请使用网文常用的架空代称（如：魔都、燕京、华夏、樱花国）。{naming_rules}

JSON 格式：
{{
  "locations": [
    {{
      "id": "稳定id，全书唯一",
      "name": "地点名",
      "type": "城市/建筑/区域/特殊场所",
      "description": "地点描述，单行文本",
      "parent_id": null,
      "connections": [
        {{
          "target": "目标地点名",
          "relation": "连接类型（包含/相邻/通往等，勿用位于）",
          "description": "连接的详细描述"
        }}
      ]
    }}
  ]
}}"""

        user_prompt = f"""故事创意：{premise}

已有世界观：
{wb_summary}

已有人物：
{char_summary}

请基于世界观和人物生成完整地图。{naming_rules}

请按照以下json格式进行输出，可以被Python json.loads函数解析。只给出JSON，不作解释，不作答：
```json
{{
  "locations": []
}}
```"""

        return await self._call_llm_and_parse_with_retry(system_prompt, user_prompt, max_tokens=4000)

    def _summarize_worldbuilding(self, wb: Dict[str, Any]) -> str:
        """总结世界观为文本"""
        if not wb:
            return "无"

        parts = []
        for key, value in wb.items():
            if isinstance(value, dict):
                items = ", ".join([f"{k}: {v}" for k, v in value.items() if v])
                parts.append(f"{key}: {items}")
        return "\n".join(parts)

    async def _call_llm_and_parse(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> Dict[str, Any]:
        """调用 LLM 并解析 JSON"""
        logger.info(f"=== 开始调用 LLM ===")
        logger.info(f"System prompt 长度: {len(system_prompt)} chars")
        logger.info(f"User prompt 长度: {len(user_prompt)} chars")
        logger.info(f"Max tokens: {max_tokens}")
        
        prompt = Prompt(system=system_prompt, user=user_prompt)
        config = GenerationConfig(max_tokens=max_tokens, temperature=1.0)
        
        logger.info(f"正在调用 LLM 服务...")
        try:
            result = await self.llm_service.generate(prompt, config)
            logger.info(f"LLM 调用成功")
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

        content = result.content or ""
        logger.info(f"LLM 返回内容长度: {len(content)} chars")
        
        if len(content) < 50:
            logger.warning(f"LLM 返回内容过短: '{content[:200]}'")
        
        try:
            parsed = parse_json_from_response(content)
            if not isinstance(parsed, dict):
                logger.error(f"解析结果不是字典: {type(parsed)}")
                raise ValueError("LLM JSON payload must be an object")
            
            logger.info(f"JSON 解析成功，解析结果: {list(parsed.keys())}")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败")
            logger.error(f"Content length: {len(content)}")
            logger.error(f"Error: {e}")
            logger.error(f"Raw content (first 1000 chars): {content[:1000]}")
            logger.error(f"Raw content (last 500 chars): {content[-500:]}")
            raise
        except Exception as e:
            logger.error(f"解析过程异常: {e}")
            raise

    async def _call_llm_and_parse_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """带重试的LLM调用 - 增强JSON输出稳定性"""
        logger.info(f"=== 开始 LLM 重试调用 ===")
        logger.info(f"最大重试次数: {max_retries}")
        logger.info(f"Max tokens: {max_tokens}")
        
        last_error = None

        for attempt in range(max_retries):
            logger.info(f"--- 尝试 {attempt + 1}/{max_retries} ---")
            try:
                if attempt == 0:
                    logger.info(f"首次调用，开始 LLM 调用")
                    parsed = await self._call_llm_and_parse(system_prompt, user_prompt, max_tokens=max_tokens)
                else:
                    retry_reminder = "\n\n【重要提醒】上次JSON解析失败，请严格遵守JSON输出规则！只输出纯JSON，不要任何其他文字！"
                    logger.warning(f"JSON解析重试 {attempt}/{max_retries}，添加强调提示")
                    parsed = await self._call_llm_and_parse(
                        system_prompt + retry_reminder,
                        user_prompt,
                        max_tokens=max_tokens
                    )
                
                if parsed:
                    logger.info(f"尝试 {attempt + 1} 成功，解析结果 keys: {list(parsed.keys())}")
                    return parsed
                
                logger.error(f"尝试 {attempt + 1} 失败：返回空对象")
                raise ValueError("LLM returned empty JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(f"尝试 {attempt + 1}/{max_retries} - JSON解析/数据验证失败: {str(e)[:200]}")
            except Exception as e:
                last_error = e
                logger.error(f"尝试 {attempt + 1}/{max_retries} - 异常: {e}", exc_info=True)

        if last_error is not None:
            logger.error(f"=== 所有 {max_retries} 次重试都失败 ===")
            logger.error(f"最后一次错误: {last_error}", exc_info=True)
        else:
            logger.error(f"=== 所有 {max_retries} 次重试都失败，无错误信息 ===")
        
        logger.error(f"返回空字典")
        return {}

    async def _generate_character_triples(self, novel_id: str, character_ids: list):
        """从人物关系生成三元组"""
        logger.info(f"Generating character relationship triples for {novel_id}")

        # 创建人物名称到ID的映射
        name_to_id = {char_data["name"]: char_id for char_id, char_data in character_ids}
        id_to_char = {cid: data for cid, data in character_ids}

        for char_id, char_data in character_ids:
            relationships = char_data.get("relationships", [])
            if not relationships:
                continue

            for rel in relationships:
                # 支持两种格式：字符串或对象
                if isinstance(rel, str):
                    # 旧格式：字符串描述，尝试解析
                    target_name = None
                    predicate = "关系"
                    description = rel

                    # 简单的名称匹配
                    for other_id, other_data in character_ids:
                        if other_id != char_id and other_data["name"] in rel:
                            target_name = other_data["name"]
                            break

                    # 提取关系类型
                    if "师徒" in rel or "师从" in rel:
                        predicate = "师徒关系"
                    elif "朋友" in rel or "好友" in rel:
                        predicate = "朋友"
                    elif "敌对" in rel or "对手" in rel:
                        predicate = "敌对"
                    elif "家人" in rel or "亲属" in rel:
                        predicate = "家人"
                    elif "同事" in rel or "同僚" in rel:
                        predicate = "同事"
                else:
                    # 新格式：对象 {target, relation, description}
                    target_name = rel.get("target")
                    predicate = rel.get("relation", "关系")
                    description = rel.get("description", "")

                # 查找目标人物ID
                target_char_id = name_to_id.get(target_name)

                # 如果找到了目标人物，创建三元组
                if target_char_id:
                    target_char = id_to_char.get(target_char_id, {})
                    subj_imp = _infer_character_importance(char_data)
                    obj_imp = _infer_character_importance(target_char)
                    triple = Triple(
                        id=f"triple-{uuid.uuid4().hex[:8]}",
                        novel_id=novel_id,
                        subject_type="character",
                        subject_id=char_id,
                        predicate=predicate,
                        object_type="character",
                        object_id=target_char_id,
                        confidence=0.9,
                        source_type=SourceType.BIBLE_GENERATED,
                        description=description,
                        attributes={
                            "subject_label": char_data["name"],
                            "object_label": target_name,
                            "subject_importance": subj_imp,
                            "object_importance": obj_imp,
                        },
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    try:
                        await self.triple_repository.save(triple)
                        logger.info(f"Created triple: {char_data['name']} -{predicate}-> {target_name}")
                    except Exception as e:
                        logger.error(f"Failed to save triple: {e}")

    async def _generate_location_triples(self, novel_id: str, location_ids: list):
        """从地点连接生成三元组"""
        logger.info(f"Generating location connection triples for {novel_id}")

        # 创建地点名称到ID的映射
        name_to_id = {loc_data["name"]: loc_id for loc_id, loc_data in location_ids}
        id_to_loc = {lid: data for lid, data in location_ids}

        for loc_id, loc_data in location_ids:
            connections = loc_data.get("connections", [])
            if not connections:
                continue

            for conn in connections:
                # 支持两种格式：字符串或对象
                if isinstance(conn, str):
                    # 旧格式：字符串描述，尝试解析
                    target_name = None
                    predicate = "连接"
                    description = conn

                    # 简单的名称匹配
                    for other_id, other_data in location_ids:
                        if other_id != loc_id and other_data["name"] in conn:
                            target_name = other_data["name"]
                            break

                    # 提取连接类型
                    if "包含" in conn or "内部" in conn:
                        predicate = "包含"
                    elif "相邻" in conn or "毗邻" in conn:
                        predicate = "相邻"
                    elif "通往" in conn or "通向" in conn:
                        predicate = "通往"
                    elif "位于" in conn:
                        predicate = "位于"
                else:
                    # 新格式：对象 {target, relation, description}
                    target_name = conn.get("target")
                    predicate = conn.get("relation", "连接")
                    description = conn.get("description", "")

                pred_norm = (predicate or "").strip()
                if pred_norm == "位于":
                    continue

                # 查找目标地点ID
                target_loc_id = name_to_id.get(target_name)

                # 如果找到了目标地点，创建三元组
                if target_loc_id:
                    target_loc = id_to_loc.get(target_loc_id, {})
                    subj_lt = _map_location_kind(loc_data.get("type", ""))
                    obj_lt = _map_location_kind(target_loc.get("type", ""))
                    subj_imp = _default_location_importance(loc_data)
                    obj_imp = _default_location_importance(target_loc)
                    triple = Triple(
                        id=f"triple-{uuid.uuid4().hex[:8]}",
                        novel_id=novel_id,
                        subject_type="location",
                        subject_id=loc_id,
                        predicate=predicate,
                        object_type="location",
                        object_id=target_loc_id,
                        confidence=0.9,
                        source_type=SourceType.BIBLE_GENERATED,
                        description=description,
                        attributes={
                            "subject_label": loc_data["name"],
                            "object_label": target_name,
                            "subject_importance": subj_imp,
                            "subject_location_type": subj_lt,
                            "object_importance": obj_imp,
                            "object_location_type": obj_lt,
                        },
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    try:
                        await self.triple_repository.save(triple)
                        logger.info(f"Created triple: {loc_data['name']} -{predicate}-> {target_name}")
                    except Exception as e:
                        logger.error(f"Failed to save triple: {e}")

    async def generate_full_character_card(
        self,
        novel_id: str,
        character_id: str,
        character_name: str
    ) -> Dict[str, Any]:
        """为指定角色生成完整的角色卡（供后台任务调用）
        
        Args:
            novel_id: 小说ID
            character_id: 角色ID
            character_name: 角色名称
            
        Returns:
            {
                "success": bool,
                "character_id": str,
                "data": Dict[str, Any] | None,
                "error": str | None
            }
        """
        try:
            logger.info(f"开始生成角色完整信息：{character_name} (ID: {character_id})")
            
            # 1. 获取 Bible 和世界观
            bible = self.bible_service.get_bible_by_novel(novel_id)
            if not bible:
                return {
                    "success": False,
                    "character_id": character_id,
                    "data": None,
                    "error": f"Bible not found for novel {novel_id}"
                }
            
            # 2. 获取世界观数据
            worldbuilding = {}
            if hasattr(bible, 'worldbuilding') and bible.worldbuilding:
                worldbuilding = bible.worldbuilding
            else:
                # 尝试从 WorldbuildingService 获取
                if self.worldbuilding_service:
                    wb_data = self.worldbuilding_service.get_worldbuilding_by_novel(novel_id)
                    if wb_data:
                        worldbuilding = wb_data
            
            # 3. 获取所有角色列表
            all_characters = []
            for char in bible.characters:
                all_characters.append({
                    "name": char.name,
                    "role": getattr(char, 'role', ''),
                    "description": char.description
                })
            
            # 4. 找到目标角色的基础信息
            target_char = None
            for char in bible.characters:
                if char.id.value == character_id or char.name == character_name:
                    target_char = char
                    break
            
            if not target_char:
                return {
                    "success": False,
                    "character_id": character_id,
                    "data": None,
                    "error": f"Character not found: {character_name}"
                }
            
            # 5. 构建基础角色数据
            char_data = {
                "name": target_char.name,
                "role": getattr(target_char, 'role', ''),
                "description": target_char.description
            }
            
            # 6. 调用 AI 生成完整角色卡
            full_card = await self._generate_full_character_card(
                char_data=char_data,
                worldbuilding=worldbuilding,
                all_characters=all_characters
            )
            
            # 7. 合并基础信息和完整信息
            full_card["name"] = target_char.name
            full_card["role"] = char_data.get("role", "")
            
            # 8. 更新 Bible 中的角色
            from domain.bible.entities.character import Character
            from domain.bible.value_objects.character_id import CharacterId
            
            updated_character = Character(
                id=target_char.id,
                name=target_char.name,
                description=target_char.description,
                relationships=target_char.relationships,
                first_appearance_chapter=getattr(target_char, 'first_appearance_chapter', None),
                # 基本信息
                role=full_card.get("role", ""),
                gender=full_card.get("gender", ""),
                age=full_card.get("age", ""),
                identity=full_card.get("identity", ""),
                appearance=full_card.get("appearance", ""),
                # 性格特征
                personality=full_card.get("personality", ""),
                strengths=full_card.get("strengths", ""),
                weaknesses=full_card.get("weaknesses", ""),
                habits=full_card.get("habits", ""),
                # 背景故事
                background=full_card.get("background", ""),
                motivation=full_card.get("motivation", ""),
                goal=full_card.get("goal", ""),
                # 能力体系
                power_system=full_card.get("power_system", ""),
                skills=full_card.get("skills", ""),
                equipment=full_card.get("equipment", ""),
                # 发展轨迹
                character_arc=full_card.get("character_arc", ""),
                # 声线锚点
                mental_state=full_card.get("mental_state", "NORMAL"),
                verbal_tic=full_card.get("verbal_tic", ""),
                idle_behavior=full_card.get("idle_behavior", ""),
            )
            
            # 9. 替换 Bible 中的角色
            bible.remove_character(target_char.id)
            bible.add_character(updated_character)
            
            # 10. 保存 Bible
            from application.world.services.bible_service import BibleService
            if isinstance(self.bible_service, BibleService):
                self.bible_service.update_bible(bible)
            
            logger.info(f"角色卡补全成功：{character_name}")
            
            return {
                "success": True,
                "character_id": character_id,
                "data": full_card,
                "error": None
            }
        
        except Exception as e:
            logger.error(f"角色卡补全失败：{character_name} - {e}", exc_info=True)
            return {
                "success": False,
                "character_id": character_id,
                "data": None,
                "error": str(e)
            }

