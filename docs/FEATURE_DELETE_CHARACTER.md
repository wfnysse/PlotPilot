# 删除角色功能实现文档

## 功能概述

实现了安全的角色删除功能，在删除前会全面检查角色的所有引用，确保不会误删重要角色。

---

## 核心特性

### ✅ 安全检查

删除角色前会自动检查以下引用：

1. **章节引用** - 角色在哪些章节中出现过
   - 出场次数统计
   - 关系类型（appears/mentioned）
   - 显示涉及的章节列表

2. **角色关系** - 其他角色是否与此角色有关联
   - 检查 relationships 字段
   - 显示关联的角色名称

3. **重要性检查** - 是否是主角或重要角色
   - 检测 role 字段（主角/protagonist）

### ✅ 用户友好的提示

- **有引用时**：显示详细的引用信息，阻止删除
- **无引用时**：弹出确认框，防止误操作
- **错误处理**：清晰的错误提示信息

---

## API 接口

### 1. 检查角色引用

```http
GET /api/v1/bible/novels/{novel_id}/bible/characters/{character_id}/references
```

**响应示例：**

```json
{
  "success": true,
  "character": {
    "id": "char_123",
    "name": "张三",
    "role": "配角"
  },
  "references": {
    "chapter_count": 5,
    "total_appearances": 8,
    "chapters": [
      {
        "chapter_id": "chapter_001",
        "chapter_number": 1,
        "chapter_title": "初遇",
        "appearance_count": 2,
        "relation_types": ["appears"]
      }
    ],
    "relationship_count": 2,
    "relationships": [
      {
        "source_character_id": "char_456",
        "source_character_name": "李四",
        "relationship": {"target_id": "char_123", "relation": "朋友"}
      }
    ],
    "is_important_character": false
  },
  "can_delete": false
}
```

### 2. 删除角色

```http
DELETE /api/v1/bible/novels/{novel_id}/bible/characters/{character_id}
Content-Type: application/json

{
  "force_delete": false
}
```

**成功响应：**

```json
{
  "success": true,
  "message": "成功删除角色: 张三",
  "deleted_character": {
    "id": "char_123",
    "name": "张三"
  }
}
```

**失败响应（有引用）：**

```json
{
  "error": "character_has_references",
  "message": "角色 '张三' 在 8 个章节元素中被引用，无法删除",
  "reference_count": 8,
  "suggestion": "请先删除所有章节中的角色引用，或使用 force_delete=true 强制删除"
}
```

---

## 前端实现

### UI 交互流程

1. **点击删除按钮** → 触发 `handleDeleteCharacter`
2. **检查引用** → 调用 `checkCharacterReferences` API
3. **判断结果**：
   - ❌ 有引用 → 显示警告对话框，列出详细信息
   - ✅ 无引用 → 弹出确认框
4. **用户确认** → 执行删除
5. **刷新列表** → 重新加载角色列表

### 代码位置

- **API 封装**: `frontend/src/api/bible.ts`
  - `checkCharacterReferences(novelId, characterId)`
  - `deleteCharacter(novelId, characterId, options)`

- **UI 组件**: `frontend/src/components/panels/CharacterCardsPanel.vue`
  - `handleDeleteCharacter(char)` - 删除处理函数
  - `<n-popconfirm>` - 确认对话框

---

## 后端实现

### 1. 引用检查端点

**文件**: `interfaces/api/v1/world/bible.py`

**函数**: `check_character_references()`

**检查逻辑**：

```python
# 1. 获取 Bible DTO
bible = bible_service.get_bible_by_novel(novel_id)

# 2. 查找角色
character = find_character(bible.characters, character_id)

# 3. 检查章节引用
from infrastructure.persistence.database.chapter_element_repository import ChapterElementRepository
chapter_references = await chapter_element_repo.get_by_element(
    ElementType.CHARACTER,
    character.id
)

# 4. 获取章节详情
for chapter_id in unique_chapter_ids:
    chapter = story_node_repo.get_by_id(chapter_id)
    # 构建章节信息列表

# 5. 检查角色关系
for char in bible.characters:
    if char.id != character.id and char.relationships:
        for rel in char.relationships:
            if rel.target_id == character.id:
                relationships.append(...)

# 6. 返回检查结果
return {
    "can_delete": len(chapter_references) == 0 and len(relationships) == 0,
    "references": {...}
}
```

### 2. 删除角色端点

**函数**: `delete_character()`

**删除逻辑**：

```python
# 1. 获取 Bible 领域实体（不是 DTO！）
from infrastructure.persistence.database.sqlite_bible_repository import SqliteBibleRepository
from infrastructure.persistence.database.connection import DatabaseConnection
from infrastructure.config import Settings

settings = Settings()
db = DatabaseConnection(settings.SQLITE_DB_PATH)
repo = SqliteBibleRepository(db)
bible = repo.get_by_novel_id(NovelId(novel_id))

# 2. 查找角色
character = find_character(bible.characters, character_id)

# 3. 安全检查（除非 force_delete=true）
if not force_delete:
    # 检查章节引用
    chapter_references = await chapter_element_repo.get_by_element(...)
    if len(chapter_references) > 0:
        raise HTTPException(400, detail={...})
    
    # 检查角色关系
    check_relationships(bible.characters, character)

# 4. 删除角色
deleted_character = bible.characters.pop(character_index)

# 5. 保存 Bible
repo.save(bible)

# 6. 返回结果
return {"success": True, "message": f"成功删除角色: {deleted_character.name}"}
```

---

## 关键技术点

### DDD 架构注意事项

⚠️ **重要**：Service 和 Repository 的区别

| 层级 | 返回类型 | 用途 | 可修改 |
|------|---------|------|--------|
| Service | DTO | 数据展示 | ❌ 不可直接修改保存 |
| Repository | Entity | 业务逻辑 | ✅ 可以修改并保存 |

**正确做法**：

```python
# 先获取 db 连接（参考上文）
# ✅ 删除操作需要使用 Repository 获取领域实体
repo = SqliteBibleRepository(db)
bible = repo.get_by_novel_id(NovelId(novel_id))
# bible.characters 是 Character 实体列表
character = bible.characters[i]
bible.characters.pop(i)
repo.save(bible)
```

**错误做法**：

```python
# ❌ Service 返回的是 DTO，不能修改后保存
bible_service = BibleService()
bible = bible_service.get_bible_by_novel(novel_id)
# bible.characters 是 CharacterDTO 列表
bible.characters.pop(i)  # 这会报错！
```

### 数据库表结构

**chapter_elements 表**：

```sql
CREATE TABLE chapter_elements (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL,
    element_type TEXT NOT NULL CHECK(element_type IN ('character', 'location', ...)),
    element_id TEXT NOT NULL,
    relation_type TEXT NOT NULL CHECK(relation_type IN ('appears', 'mentioned', ...)),
    importance TEXT DEFAULT 'normal',
    appearance_order INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES story_nodes(id) ON DELETE CASCADE,
    UNIQUE(chapter_id, element_type, element_id, relation_type)
);

CREATE INDEX idx_chapter_elements_element ON chapter_elements(element_type, element_id);
```

**查询角色引用**：

```sql
SELECT * FROM chapter_elements
WHERE element_type = 'character' AND element_id = ?
ORDER BY created_at
```

---

## 测试步骤

### 1. 测试无引用的角色删除

1. 创建一个新角色（不添加到任何章节）
2. 点击角色卡片上的"删除"按钮
3. 应该弹出确认框："确定要删除角色 'XXX' 吗？"
4. 点击"删除"
5. 角色应该被成功删除，显示成功消息

### 2. 测试有章节引用的角色删除

1. 选择一个已在章节中出现的角色
2. 点击"删除"按钮
3. 应该显示警告对话框，包含：
   - 该角色在 X 个章节中出现过
   - 共计 Y 次出场
   - 涉及章节列表（最多显示 5 个）
4. 不应该执行删除

### 3. 测试有角色关系的角色删除

1. 选择一个与其他角色有关联的角色
2. 点击"删除"按钮
3. 应该显示警告：
   - 有 X 个其他角色与此角色有关联
   - 列出关联的角色名称
4. 不应该执行删除

### 4. 测试强制删除（可选）

如果需要实现强制删除功能：

```typescript
// 前端添加选项
const forceDelete = await window.confirm(
  '该角色有引用，是否强制删除？\n\n注意：这可能导致数据不一致！'
)

if (forceDelete) {
  await bibleApi.deleteCharacter(novelId, charId, { force_delete: true })
}
```

---

## 可能的改进

### 1. 级联删除

当删除角色时，自动清理相关数据：

- 从 `chapter_elements` 表中删除该角色的所有记录
- 从其他角色的 `relationships` 中移除此角色
- 从知识图谱中删除相关三元组

### 2. 软删除

不真正删除角色，而是标记为已删除：

```python
@dataclass
class Character:
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
```

优点：
- 可以恢复误删的角色
- 保留历史记录
- 避免外键约束问题

### 3. 批量删除

支持一次删除多个角色：

```typescript
const selectedCharacters = ref<CharacterDTO[]>([])

async function handleBatchDelete() {
  for (const char of selectedCharacters.value) {
    await handleDeleteCharacter(char)
  }
}
```

### 4. 删除日志

记录所有删除操作：

```python
logger.info(f"User {user_id} deleted character {character_id} from novel {novel_id}")
```

---

## 相关文件清单

### 后端

- ✅ `interfaces/api/v1/world/bible.py`
  - `check_character_references()` - 检查引用
  - `delete_character()` - 删除角色

- ✅ `infrastructure/persistence/database/chapter_element_repository.py`
  - `get_by_element()` - 查询元素引用

- ✅ `infrastructure/persistence/database/sqlite_story_node_repository.py`
  - `get_by_id()` - 获取章节详情

### 前端

- ✅ `frontend/src/api/bible.ts`
  - `checkCharacterReferences()` - API 封装
  - `deleteCharacter()` - API 封装

- ✅ `frontend/src/components/panels/CharacterCardsPanel.vue`
  - `handleDeleteCharacter()` - 删除处理函数
  - `<n-popconfirm>` - 确认对话框 UI

---

## 总结

✅ **已实现的功能**：

1. ✅ 完整的引用检查（章节 + 角色关系）
2. ✅ 详细的警告信息（显示具体引用）
3. ✅ 用户确认机制（防止误操作）
4. ✅ 清晰的错误提示
5. ✅ 安全的删除流程

🎯 **核心价值**：

- **数据安全**：不会误删重要角色
- **用户体验**：清晰的提示信息
- **代码质量**：遵循 DDD 架构原则

📝 **注意事项**：

- 删除操作不可恢复（除非实现软删除）
- 需要确保 `chapter_elements` 表有正确的索引
- 建议在生产环境添加删除日志
