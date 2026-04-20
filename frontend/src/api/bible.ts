import { apiClient } from './config'

/** Bible 人物关系：字符串 或 LLM 结构化对象 */
export type BibleRelationshipEntry =
  | string
  | { target?: string; relation?: string; description?: string }

export interface CharacterDTO {
  id: string
  name: string
  description: string
  relationships: BibleRelationshipEntry[]
  /** AI 生成时的角色定位（主角/配角等） */
  role?: string
  mental_state?: string
  verbal_tic?: string
  idle_behavior?: string
  
  // 【角色卡扩展】基本信息
  gender?: string
  age?: string
  identity?: string
  appearance?: string
  
  // 【角色卡扩展】性格特征
  personality?: string
  strengths?: string
  weaknesses?: string
  habits?: string
  
  // 【角色卡扩展】背景故事
  background?: string
  motivation?: string
  goal?: string
  
  // 【角色卡扩展】能力体系
  power_system?: string
  skills?: string
  equipment?: string
  
  // 【角色卡扩展】发展轨迹
  character_arc?: string
}

export interface WorldSettingDTO {
  id: string
  name: string
  description: string
  setting_type: string
}

export interface LocationDTO {
  id: string
  name: string
  description: string
  location_type: string
}

export interface TimelineNoteDTO {
  id: string
  event: string
  time_point: string
  description: string
}

export interface StyleNoteDTO {
  id: string
  category: string
  content: string
}

export interface BibleDTO {
  id: string
  novel_id: string
  characters: CharacterDTO[]
  world_settings: WorldSettingDTO[]
  locations: LocationDTO[]
  timeline_notes: TimelineNoteDTO[]
  style_notes: StyleNoteDTO[]
}

export interface BibleGenerationProgress {
  novel_id: string
  stage: string
  current_step: number
  total_steps: number
  message: string
  progress: number
  updated_at: string
}

export interface AddCharacterRequest {
  character_id: string
  name: string
  description: string
}

export const bibleApi = {
  /**
   * Create bible for a novel
   * POST /api/v1/bible/novels/{novelId}/bible
   */
  createBible: (novelId: string, bibleId: string) =>
    apiClient.post<BibleDTO>(`/bible/novels/${novelId}/bible`, {
      bible_id: bibleId,
      novel_id: novelId,
    }) as Promise<BibleDTO>,

  /**
   * Get bible by novel ID
   * GET /api/v1/bible/novels/{novelId}/bible
   */
  getBible: (novelId: string) =>
    apiClient.get<BibleDTO>(`/bible/novels/${novelId}/bible`) as Promise<BibleDTO>,

  /**
   * List all characters in a bible
   * GET /api/v1/bible/novels/{novelId}/bible/characters
   */
  listCharacters: (novelId: string) =>
    apiClient.get<CharacterDTO[]>(`/bible/novels/${novelId}/bible/characters`) as Promise<CharacterDTO[]>,

  /**
   * Add character to bible
   * POST /api/v1/bible/novels/{novelId}/bible/characters
   */
  addCharacter: (novelId: string, data: AddCharacterRequest) =>
    apiClient.post<BibleDTO>(`/bible/novels/${novelId}/bible/characters`, data) as Promise<BibleDTO>,

  /**
   * Update character card
   * PUT /api/v1/bible/novels/{novelId}/bible/characters/{characterId}
   */
  updateCharacter: (
    novelId: string,
    characterId: string,
    data: Partial<CharacterDTO>
  ) =>
    apiClient.put<BibleDTO>(`/bible/novels/${novelId}/bible/characters/${characterId}`, data) as Promise<BibleDTO>,

  /**
   * Confirm and save characters with full character cards
   * POST /api/v1/bible/novels/{novelId}/bible/characters/confirm
   */
  confirmCharacters: (
    novelId: string,
    data: {
      characters: any[]
      generate_full_card?: boolean
    }
  ) =>
    apiClient.post<any>(`/bible/novels/${novelId}/bible/characters/confirm`, data) as Promise<any>,

  /**
   * Add world setting to bible
   * POST /api/v1/bible/novels/{novelId}/bible/world-settings
   */
  addWorldSetting: (
    novelId: string,
    data: { setting_id: string; name: string; description: string; setting_type: string }
  ) =>
    apiClient.post<BibleDTO>(`/bible/novels/${novelId}/bible/world-settings`, data) as Promise<BibleDTO>,

  /**
   * Bulk update entire bible
   * PUT /api/v1/bible/novels/{novelId}/bible
   */
  updateBible: (
    novelId: string,
    data: {
      characters: CharacterDTO[]
      world_settings: WorldSettingDTO[]
      locations: LocationDTO[]
      timeline_notes: TimelineNoteDTO[]
      style_notes: StyleNoteDTO[]
    }
  ) =>
    apiClient.put<BibleDTO>(`/bible/novels/${novelId}/bible`, data) as Promise<BibleDTO>,

  /**
   * AI generate (or regenerate) Bible for a novel
   * POST /api/v1/bible/novels/{novelId}/generate
   */
  /** 后端 202 即返回，但冷启动/代理连后端较慢时默认 30s 不够，增加到 5 分钟 */
  generateBible: (novelId: string, stage: string = 'all') => {
    console.log(`[API] generateBible called with novelId=${novelId}, stage=${stage}`)
    const promise = apiClient.post<{ message: string; novel_id: string; status_url: string }>(
      `/bible/novels/${novelId}/generate?stage=${stage}`,
      {},
      { timeout: 300_000 }  // 5 分钟
    ) as Promise<{ message: string; novel_id: string; status_url: string }>
    
    promise.then(
      (result) => console.log(`[API] generateBible successful:`, result),
      (error) => console.error(`[API] generateBible failed:`, error)
    )
    
    return promise
  },

  /**
   * Check Bible generation status
   * GET /api/v1/bible/novels/{novelId}/bible/status
   */
  getBibleStatus: (novelId: string) =>
    apiClient.get<{ exists: boolean; ready: boolean; novel_id: string }>(
      `/bible/novels/${novelId}/bible/status`,
      { timeout: 60_000 }
    ) as Promise<{ exists: boolean; ready: boolean; novel_id: string }>,

  /**
   * Get Bible generation real-time progress
   * GET /api/v1/bible/novels/{novelId}/generate/progress
   */
  getGenerationProgress: (novelId: string) =>
    apiClient.get<{ progress: BibleGenerationProgress | null }>(
      `/bible/novels/${novelId}/generate/progress`,
      { timeout: 30_000 }
    ) as Promise<{ progress: BibleGenerationProgress | null }>,

  /**
   * Complete character card with AI
   * POST /api/v1/bible/novels/{novelId}/bible/characters/{characterId}/complete
   */
  completeCharacterCard: (
    novelId: string,
    characterId: string,
    data?: { generate_full_card?: boolean }
  ) =>
    apiClient.post<any>(
      `/bible/novels/${novelId}/bible/characters/${characterId}/complete`,
      data || {},
      { timeout: 120_000 }
    ) as Promise<any>,

  /**
   * Check character references before deletion
   * GET /api/v1/bible/novels/{novelId}/bible/characters/{characterId}/references
   */
  checkCharacterReferences: (novelId: string, characterId: string) =>
    apiClient.get<any>(`/bible/novels/${novelId}/bible/characters/${characterId}/references`) as Promise<any>,

  /**
   * Delete character from bible
   * DELETE /api/v1/bible/novels/{novelId}/bible/characters/{characterId}
   */
  deleteCharacter: (
    novelId: string,
    characterId: string,
    data?: { force_delete?: boolean }
  ) =>
    apiClient.delete<any>(
      `/bible/novels/${novelId}/bible/characters/${characterId}`,
      { data: data || {} }
    ) as Promise<any>,
}
