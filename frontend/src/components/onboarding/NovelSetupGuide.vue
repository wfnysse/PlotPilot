<template>
  <n-modal
    v-model:show="modalOpen"
    :mask-closable="false"
    :close-on-esc="false"
    :closable="true"
    preset="card"
    title="新书设置向导"
    style="width: 90%; max-width: 900px; max-height: 90vh"
  >
    <n-steps :current="currentStep" :status="stepStatus" size="medium">
      <n-step title="世界观" description="5维度框架" />
      <n-step title="人物" description="主要角色" />
      <n-step title="地图" description="地图系统" />
      <n-step title="故事线" description="主线支线" />
      <n-step title="情节弧" description="剧情曲线" />
      <n-step title="开始" description="进入工作台" />
    </n-steps>

    <div class="step-content">
      <!-- Step 1: Generate Worldbuilding + Style -->
      <div v-if="currentStep === 1" class="step-panel">
        <n-alert v-if="bibleError" type="error" :title="bibleError" style="margin-bottom: 16px" />
        <n-spin :show="generatingBible">
          <div v-if="!bibleGenerated" class="step-info">
            <n-icon size="48" color="#18a058">
              <IconBook />
            </n-icon>
            <h3>{{ bibleStatusText }}</h3>
            
            <!-- 进度条 -->
            <n-progress
              v-if="generatingBible"
              type="line"
              :percentage="bibleProgress || 1"
              :show-indicator="true"
              status="success"
              style="margin-top: 16px"
            />
            
            <p class="step-subtitle">{{ bibleStatusSubtitle }}</p>
          </div>

          <!-- 生成完成后显示预览 -->
          <div v-else class="bible-preview">
            <n-alert type="success" title="世界观生成完成" style="margin-bottom: 16px">
              请查看并确认世界观设定和文风公约，下一步将基于此生成人物和地点。
            </n-alert>

            <n-collapse :default-expanded-names="['worldbuilding', 'style']">
              <n-collapse-item title="世界观（5维度框架）" name="worldbuilding">
                <n-space vertical>
                  <n-card size="small" title="核心法则">
                    <n-space vertical size="small">
                      <div><strong>力量体系：</strong>{{ worldbuildingData.core_rules?.power_system || '待生成' }}</div>
                      <div><strong>物理规律：</strong>{{ worldbuildingData.core_rules?.physics_rules || '待生成' }}</div>
                      <div><strong>魔法/科技：</strong>{{ worldbuildingData.core_rules?.magic_tech || '待生成' }}</div>
                    </n-space>
                  </n-card>
                  <n-card size="small" title="地理生态">
                    <n-space vertical size="small">
                      <div><strong>地形：</strong>{{ worldbuildingData.geography?.terrain || '待生成' }}</div>
                      <div><strong>气候：</strong>{{ worldbuildingData.geography?.climate || '待生成' }}</div>
                      <div><strong>资源：</strong>{{ worldbuildingData.geography?.resources || '待生成' }}</div>
                      <div><strong>生态：</strong>{{ worldbuildingData.geography?.ecology || '待生成' }}</div>
                    </n-space>
                  </n-card>
                  <n-card size="small" title="社会结构">
                    <n-space vertical size="small">
                      <div><strong>政治：</strong>{{ worldbuildingData.society?.politics || '待生成' }}</div>
                      <div><strong>经济：</strong>{{ worldbuildingData.society?.economy || '待生成' }}</div>
                      <div><strong>阶级：</strong>{{ worldbuildingData.society?.class_system || '待生成' }}</div>
                    </n-space>
                  </n-card>
                  <n-card size="small" title="历史文化">
                    <n-space vertical size="small">
                      <div><strong>历史：</strong>{{ worldbuildingData.culture?.history || '待生成' }}</div>
                      <div><strong>宗教：</strong>{{ worldbuildingData.culture?.religion || '待生成' }}</div>
                      <div><strong>禁忌：</strong>{{ worldbuildingData.culture?.taboos || '待生成' }}</div>
                    </n-space>
                  </n-card>
                  <n-card size="small" title="沉浸感细节">
                    <n-space vertical size="small">
                      <div><strong>衣食住行：</strong>{{ worldbuildingData.daily_life?.food_clothing || '待生成' }}</div>
                      <div><strong>俚语口音：</strong>{{ worldbuildingData.daily_life?.language_slang || '待生成' }}</div>
                      <div><strong>娱乐方式：</strong>{{ worldbuildingData.daily_life?.entertainment || '待生成' }}</div>
                    </n-space>
                  </n-card>
                </n-space>
              </n-collapse-item>

              <n-collapse-item title="文风公约" name="style">
                <n-card size="small">
                  <div class="style-convention-text">{{ styleConventionDisplay || '待生成' }}</div>
                </n-card>
              </n-collapse-item>
            </n-collapse>
          </div>
        </n-spin>
      </div>

      <!-- Step 2: Generate Characters -->
      <div v-else-if="currentStep === 2" class="step-panel">
        <n-alert v-if="characterError" type="error" title="角色生成失败" style="margin-bottom: 16px; width: 100%">
          <template #icon>
            <n-icon component="md-alert" />
          </template>
          <p>{{ characterError }}</p>
          <p v-if="characterErrorDetail" style="margin-top: 8px; font-size: 12px; opacity: 0.8">
            {{ characterErrorDetail }}
          </p>
          <p v-if="characterErrorHint" style="margin-top: 8px; color: #f0a020; font-size: 13px">
            💡 {{ characterErrorHint }}
          </p>
          <n-button
            v-if="!generatingCharacters"
            type="primary"
            size="small"
            style="margin-top: 12px"
            @click="retryGenerateCharacters"
          >
            重新生成
          </n-button>
        </n-alert>
        <n-spin :show="generatingCharacters">
          <div v-if="!charactersGenerated && !characterError" class="step-info">
            <n-icon size="48" color="#2080f0">
              <IconPeople />
            </n-icon>
            <h3>{{ characterStatusText }}</h3>
            <n-progress
              v-if="generatingCharacters"
              type="line"
              :percentage="characterProgress || 1"
              :show-indicator="true"
              status="info"
              style="margin-top: 16px"
            />
            <p class="step-subtitle">基于世界观设定，AI 正在生成3-5个主要角色...</p>
          </div>

          <!-- 生成完成后显示预览 -->
          <div v-else class="bible-preview">
            <n-alert type="success" title="人物生成完成" style="margin-bottom: 16px">
              请查看并确认角色设定。
            </n-alert>

            <n-list bordered>
              <n-list-item v-for="char in bibleData.characters" :key="char.name">
                <n-thing :title="char.name" :description="char.description">
                  <template #header-extra>
                    <n-tag size="small">{{ char.role }}</n-tag>
                  </template>
                </n-thing>
              </n-list-item>
            </n-list>
          </div>
        </n-spin>
      </div>

      <!-- Step 3: Generate Locations -->
      <div v-else-if="currentStep === 3" class="step-panel">
        <n-spin :show="generatingLocations">
          <div v-if="!locationsGenerated" class="step-info">
            <n-icon size="48" color="#f0a020">
              <IconMap />
            </n-icon>
            <h3>{{ locationStatusText }}</h3>
            <n-progress
              v-if="generatingLocations"
              type="line"
              :percentage="locationProgress || 1"
              :show-indicator="true"
              status="warning"
              style="margin-top: 16px"
            />
            <p class="step-subtitle">基于世界观和人物设定，AI 正在生成完整的地点系统（地图）...</p>
          </div>

          <!-- 生成完成后显示预览 -->
          <div v-else class="bible-preview">
            <n-alert type="success" title="地图生成完成" style="margin-bottom: 16px">
              请查看并确认地点设定。
            </n-alert>

            <BibleLocationsGraphPreview :locations="bibleData.locations || []" />
            <n-list bordered style="margin-top: 16px">
              <n-list-item v-for="loc in bibleData.locations" :key="loc.id || loc.name">
                <n-thing :title="loc.name" :description="loc.description">
                  <template #header-extra>
                    <n-tag size="small" type="info">{{ loc.location_type || '地点' }}</n-tag>
                  </template>
                </n-thing>
              </n-list-item>
            </n-list>
          </div>
        </n-spin>
      </div>

      <!-- Step 4: 主线候选（LLM 推演） -->
      <div v-else-if="currentStep === 4" class="step-panel step-panel--storyline">
        <div class="step-info step-info--wide">
          <n-icon size="48" color="#2080f0">
            <IconTimeline />
          </n-icon>
          <h3>确立故事主轴</h3>
          <n-progress
            v-if="plotSuggesting"
            type="line"
            :percentage="storylineProgress || 1"
            :show-indicator="true"
            status="info"
            style="margin-top: 16px; width: 100%; max-width: 400px"
          />
          <p>{{ storylineStatusText }}</p>
        </div>

        <n-alert v-if="plotSuggestError" type="error" :title="plotSuggestError" style="margin-bottom: 12px; width: 100%" />
        <n-alert v-if="mainPlotCommitted" type="success" title="已保存主线" style="margin-bottom: 12px; width: 100%">
          已进入本书的主故事线记录，可随时在工作台「设置 → 故事线」中修改。
        </n-alert>

        <n-spin :show="plotSuggesting" style="width: 100%">
          <div v-if="!customMode" class="plot-options-block">
            <n-space vertical :size="12" style="width: 100%">
              <n-card
                v-for="opt in plotOptions"
                :key="opt.id"
                size="small"
                :bordered="true"
                class="plot-option-card"
                :class="{ 'plot-option-card--disabled': mainPlotCommitted }"
              >
                <template #header>
                  <n-space align="center" :size="8">
                    <n-tag size="small" type="info" round>{{ opt.type || '主线方案' }}</n-tag>
                    <span class="plot-option-title">{{ opt.title }}</span>
                  </n-space>
                </template>
                <n-space vertical :size="8">
                  <div class="plot-line"><strong>梗概：</strong>{{ opt.logline }}</div>
                  <div v-if="opt.core_conflict" class="plot-line"><strong>核心冲突：</strong>{{ opt.core_conflict }}</div>
                  <div v-if="opt.starting_hook" class="plot-line"><strong>开篇钩子：</strong>{{ opt.starting_hook }}</div>
                  <n-button
                    type="primary"
                    size="small"
                    :loading="adoptingPlotId === opt.id"
                    :disabled="mainPlotCommitted"
                    @click="adoptPlotOption(opt)"
                  >
                    选这条作为主线
                  </n-button>
                </n-space>
              </n-card>
            </n-space>

            <n-space style="margin-top: 16px; width: 100%" justify="center" :size="12">
              <n-button secondary :disabled="mainPlotCommitted || plotSuggesting" @click="refreshPlotSuggestions">
                换一组方向
              </n-button>
              <n-button secondary :disabled="mainPlotCommitted" @click="customMode = true">
                我有自己的想法
              </n-button>
            </n-space>
          </div>

          <div v-else class="plot-custom-block">
            <n-input
              v-model:value="customLogline"
              type="textarea"
              placeholder="用一句话写下你想写的主线（例如：废柴少年为救妹妹卷入财阀灵根黑市……）"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :disabled="mainPlotCommitted"
            />
            <n-space style="margin-top: 12px" :size="8">
              <n-button :disabled="mainPlotCommitted" @click="cancelCustomMainPlot">返回候选</n-button>
              <n-button
                type="primary"
                :loading="adoptingCustom"
                :disabled="mainPlotCommitted"
                @click="adoptCustomMainPlot"
              >
                用这句话作为主线
              </n-button>
            </n-space>
          </div>
        </n-spin>
      </div>

      <!-- Step 5: Plot Arc -->
      <div v-else-if="currentStep === 5" class="step-panel">
        <n-spin :show="generatingPlotArc">
          <div v-if="!plotArcGenerated" class="step-info">
            <n-icon size="48" color="#f0a020">
              <IconChart />
            </n-icon>
            <h3>设计情节弧线</h3>
            <n-progress
              v-if="generatingPlotArc"
              type="line"
              :percentage="plotArcProgress || 1"
              :show-indicator="true"
              status="warning"
              style="margin-top: 16px"
            />
            <p>{{ plotArcStatusText }}</p>
            <n-space vertical size="small" style="margin-top: 16px; text-align: left">
              <div>• 开端：故事的起点</div>
              <div>• 上升：矛盾逐渐激化</div>
              <div>• 转折：关键转折点</div>
              <div>• 高潮：矛盾最激烈时刻</div>
              <div>• 结局：故事的收尾</div>
            </n-space>
          </div>

          <!-- 生成完成后显示预览 -->
          <div v-else class="bible-preview">
            <n-alert type="success" title="情节弧生成完成" style="margin-bottom: 16px">
              请查看并确认五幕式情节弧设定。
            </n-alert>

            <n-space vertical style="width: 100%">
              <n-card size="small" title="第一幕：开端">
                <p>{{ plotArcData.act1 || '正在生成...' }}</p>
              </n-card>
              <n-card size="small" title="第二幕：上升">
                <p>{{ plotArcData.act2 || '正在生成...' }}</p>
              </n-card>
              <n-card size="small" title="第三幕：转折">
                <p>{{ plotArcData.act3 || '正在生成...' }}</p>
              </n-card>
              <n-card size="small" title="第四幕：高潮">
                <p>{{ plotArcData.act4 || '正在生成...' }}</p>
              </n-card>
              <n-card size="small" title="第五幕：结局">
                <p>{{ plotArcData.act5 || '正在生成...' }}</p>
              </n-card>
            </n-space>
          </div>
        </n-spin>
      </div>

      <!-- Step 6: Complete -->
      <div v-else-if="currentStep === 6" class="step-panel">
        <div class="step-info">
          <n-icon size="48" color="#18a058">
            <IconCheck />
          </n-icon>
          <h3>准备就绪！</h3>
          <p>所有基础设置已完成，现在可以开始创作了。</p>
          <p style="margin-top: 12px; color: #666">您可以随时在工作台的"设置"面板中调整这些内容。</p>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="space-between">
        <n-button v-if="currentStep > 3 && currentStep < 6" @click="handleSkip">
          跳过向导
        </n-button>
        <div v-else></div>
        <n-space>
          <n-button
            v-if="(currentStep === 1 && bibleGenerated) || (currentStep === 2 && charactersGenerated) || (currentStep === 3 && locationsGenerated)"
            type="primary"
            @click="handleNext"
          >
            确认并继续
          </n-button>
          <n-button v-if="currentStep === 4" :disabled="!mainPlotCommitted" @click="handleNext"> 下一步 </n-button>
          <n-button
            v-if="currentStep === 5 && !generatingPlotArc && !plotArcGenerated"
            type="primary"
            @click="startPlotArcGeneration"
          >
            开始生成情节弧
          </n-button>
          <n-button
            v-if="currentStep === 5 && plotArcGenerated"
            type="primary"
            @click="handleNext"
          >
            完成设置
          </n-button>
          <n-button v-if="currentStep === 6" type="primary" @click="handleComplete">
            进入工作台
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>

  <!-- 角色确认弹窗 -->
  <CharacterConfirmationModal
    ref="characterConfirmModalRef"
    :novel-id="props.novelId"
    @confirm="handleCharactersConfirm"
    @cancel="handleCharactersCancel"
  />
</template>

<script setup lang="ts">
import { h, ref, watch, computed, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { bibleApi, type BibleDTO, type StyleNoteDTO } from '@/api/bible'
import { worldbuildingApi } from '@/api/worldbuilding'
import { workflowApi, type MainPlotOptionDTO } from '@/api/workflow'
import BibleLocationsGraphPreview from './BibleLocationsGraphPreview.vue'
import CharacterConfirmationModal from '../CharacterConfirmationModal.vue'

const WB_DIMS = ['core_rules', 'geography', 'society', 'culture', 'daily_life'] as const

function emptyWorldbuildingShape(): Record<(typeof WB_DIMS)[number], Record<string, string>> {
  return {
    core_rules: {},
    geography: {},
    society: {},
    culture: {},
    daily_life: {},
  }
}

function createEmptyBible(): BibleDTO {
  return {
    id: '',
    novel_id: '',
    characters: [],
    world_settings: [],
    locations: [],
    timeline_notes: [],
    style_notes: [],
  }
}

/** 从 Bible.world_settings 名如 core_rules.power_system 还原为五维对象 */
function worldbuildingFromWorldSettings(
  settings: { name: string; description?: string }[] | undefined
): Record<(typeof WB_DIMS)[number], Record<string, string>> {
  const out = emptyWorldbuildingShape()
  const dimSet = new Set<string>(WB_DIMS)
  for (const s of settings || []) {
    const dot = s.name.indexOf('.')
    if (dot < 0) continue
    const dim = s.name.slice(0, dot)
    const key = s.name.slice(dot + 1)
    if (!dimSet.has(dim) || !key) continue
    out[dim as (typeof WB_DIMS)[number]][key] = (s.description || '').trim()
  }
  return out
}

function normalizeWorldbuildingFromApi(raw: Record<string, unknown> | null | undefined) {
  const out = emptyWorldbuildingShape()
  if (!raw || typeof raw !== 'object') return out
  for (const d of WB_DIMS) {
    const block = raw[d]
    if (block && typeof block === 'object') {
      out[d] = { ...(block as Record<string, string>) }
    }
  }
  return out
}

/** world_settings 打底，API 非空字段覆盖（避免只写入 Bible 时向导全「待生成」） */
function mergeWorldbuildingDisplay(
  fromApi: ReturnType<typeof normalizeWorldbuildingFromApi>,
  fromBibleSettings: ReturnType<typeof worldbuildingFromWorldSettings>
) {
  const out = emptyWorldbuildingShape()
  for (const d of WB_DIMS) {
    const merged = { ...fromBibleSettings[d], ...fromApi[d] }
    out[d] = merged
  }
  return out
}

function styleConventionFromBible(bible: BibleDTO): string {
  const b = bible as BibleDTO & { style?: string }
  if (b.style && String(b.style).trim()) return String(b.style).trim()
  const notes: StyleNoteDTO[] = b.style_notes || []
  const conv = notes.filter(
    (n: StyleNoteDTO) => n.category === '文风公约' || (n.category || '').includes('文风')
  )
  if (conv.length) return conv.map((n: StyleNoteDTO) => (n.content || '').trim()).filter(Boolean).join('\n\n')
  if (notes.length)
    return notes
      .map((n: StyleNoteDTO) => `[${n.category || '风格'}] ${n.content || ''}`.trim())
      .join('\n\n')
  return ''
}

function formatApiError(error: unknown): string {
  const e = error as {
    response?: { data?: { detail?: unknown } }
    message?: string
  }
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d))
    return d.map((x: { msg?: string }) => x?.msg || JSON.stringify(x)).join('；')
  if (d != null && typeof d === 'object') return JSON.stringify(d)
  if (e?.message) return e.message
  return ''
}

const IconBook = () =>
  h(
    'svg',
    { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'currentColor' },
    h('path', { d: 'M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z' })
  )

const IconPeople = () =>
  h(
    'svg',
    { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'currentColor' },
    h('path', { d: 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z' })
  )

const IconMap = () =>
  h(
    'svg',
    { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'currentColor' },
    h('path', { d: 'M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z' })
  )

const IconTimeline = () =>
  h(
    'svg',
    { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'currentColor' },
    h('path', { d: 'M23 8c0 1.1-.9 2-2 2-.18 0-.35-.02-.51-.07l-3.56 3.55c.05.16.07.34.07.52 0 1.1-.9 2-2 2s-2-.9-2-2c0-.18.02-.36.07-.52l-2.55-2.55c-.16.05-.34.07-.52.07s-.36-.02-.52-.07l-4.55 4.56c.05.16.07.33.07.51 0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2c.18 0 .35.02.51.07l4.56-4.55C8.02 9.36 8 9.18 8 9c0-1.1.9-2 2-2s2 .9 2 2c0 .18-.02.36-.07.52l2.55 2.55c.16-.05.34-.07.52-.07s.36.02.52.07l3.55-3.56C19.02 8.35 19 8.18 19 8c0-1.1.9-2 2-2s2 .9 2 2z' })
  )

const IconChart = () =>
  h(
    'svg',
    { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'currentColor' },
    h('path', { d: 'M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z' })
  )

const IconCheck = () =>
  h(
    'svg',
    { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'currentColor' },
    h('path', { d: 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z' })
  )

const props = withDefaults(
  defineProps<{
    novelId: string
    show: boolean
    /** 用于主线默认章节范围 1 ~ targetChapters */
    targetChapters?: number
  }>(),
  { targetChapters: 100 }
)

const message = useMessage()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'complete'): void
  (e: 'skip'): void
}>()

/** 与父组件 show 单一数据源，避免本地 visible 与 props 打架导致误 emit(false) 把向导关掉 */
const modalOpen = computed({
  get: () => props.show,
  set: (v: boolean) => {
    if (v) {
      emit('update:show', true)
      return
    }
    requestClose()
  },
})

const currentStep = ref(1)
const stepStatus = ref<'process' | 'finish' | 'error' | 'wait'>('process')

// 第1步：生成世界观和文风
const generatingBible = ref(false)
const bibleGenerated = ref(false)
const bibleStatusText = ref('正在生成世界观...')
const bibleStatusSubtitle = ref('AI 正在分析您的故事创意，生成世界观（5维度框架）和文风公约...')
const bibleProgress = ref(0)
const bibleError = ref('')
const bibleData = ref<BibleDTO>(createEmptyBible())
const worldbuildingData = ref<ReturnType<typeof emptyWorldbuildingShape>>(emptyWorldbuildingShape())

const styleConventionDisplay = computed(() => styleConventionFromBible(bibleData.value))

// 第2步：生成人物和地点
const generatingCharacters = ref(false)
const charactersGenerated = ref(false)
const showCharacterConfirmation = ref(false)
const characterConfirmModalRef = ref<any>(null)
const characterProgress = ref(0)
const characterStatusText = ref('正在生成角色...')
const characterError = ref('')
const characterErrorDetail = ref('')
const characterErrorHint = ref('')

// 第3步：生成地点
const generatingLocations = ref(false)
const locationsGenerated = ref(false)
const locationProgress = ref(0)
const locationStatusText = ref('正在生成地点...')

// Step 4：主线推演
const plotOptions = ref<MainPlotOptionDTO[]>([])
const plotSuggesting = ref(false)
const plotSuggestError = ref('')
const mainPlotCommitted = ref(false)
const customMode = ref(false)
const customLogline = ref('')
const adoptingPlotId = ref<string | null>(null)
const adoptingCustom = ref(false)
const storylineProgress = ref(0)
const storylineStatusText = ref('基于你已确认的世界观、人物与地图，系统推演三条可选主线方向...')

// Step 5: 情节弧生成
const generatingPlotArc = ref(false)
const plotArcGenerated = ref(false)
const plotArcProgress = ref(0)
const plotArcStatusText = ref('点击按钮开始生成五幕式情节弧...')
const plotArcData = ref({ act1: '', act2: '', act3: '', act4: '', act5: '' })

const chapterEndForStoryline = computed(() => Math.max(1, props.targetChapters ?? 100))

function diagnoseCharacterGenerationError(error: unknown): { error: string; detail: string; hint: string } {
  const err = error as any
  const status = err?.response?.status
  const statusText = err?.response?.statusText || ''
  const responseData = err?.response?.data
  const errMessage = err?.message || String(error)
  
  // 网络连接问题
  if (errMessage.includes('Network Error') || 
      errMessage.includes('timeout') || 
      errMessage.includes('connect')) {
    return {
      error: '无法连接到后端服务',
      detail: errMessage,
      hint: '请确认后端服务是否正常启动，可以查看 start_services.py 窗口的日志状态'
    }
  }
  
  // HTTP 状态码检测
  if (status === 401 || status === 403) {
    return {
      error: '权限验证失败',
      detail: `HTTP ${status}: ${statusText}`,
      hint: '请检查 LLM API Key 是否正确配置，或者令牌是否过期'
    }
  }
  
  if (status === 429) {
    return {
      error: 'API 请求频率超限',
      detail: `HTTP ${status}: Too Many Requests`,
      hint: 'LLM 服务商限制了请求频率，请等待几分钟后重试，或更换 API 提供商'
    }
  }
  
  if (status >= 500) {
    const backendError = responseData?.detail || responseData?.message || statusText
    if (backendError?.includes('LLM') || backendError?.includes('token') || backendError?.includes('API')) {
      return {
        error: 'LLM 调用失败',
        detail: backendError,
        hint: '请检查 LLM 配置：1) API Key 是否正确 2) 模型名称是否正确 3) 是否有额度'
      }
    }
    return {
      error: '后端服务内部错误',
      detail: `HTTP ${status}: ${backendError || statusText}`,
      hint: '请查看后端日志窗口获取详细错误信息，可能是数据库或依赖服务异常'
    }
  }
  
  // 世界观数据为空
  if (errMessage.includes('worldbuilding') || errMessage.includes('bible') || errMessage.includes('世界观')) {
    return {
      error: '世界观数据不完整',
      detail: errMessage,
      hint: '第一步世界观生成可能未完成，请确认第一步已成功生成完整的世界观设定'
    }
  }
  
  // 默认通用错误
  return {
    error: '角色生成过程出错',
    detail: errMessage.substring(0, 150),
    hint: '可以尝试点击「重新生成」，或检查后端控制台的错误日志获取详细信息'
  }
}

async function startGenerateCharacters() {
  console.log('[NovelSetupGuide] 开始处理第2步：角色生成，novelId:', props.novelId)
  // 重置错误状态
  characterError.value = ''
  characterErrorDetail.value = ''
  characterErrorHint.value = ''
  
  // 进入第2步：生成人物
  currentStep.value = 2
  generatingCharacters.value = true
  characterProgress.value = 5
  characterStatusText.value = '正在分析世界观设定...'
  biblePollEpoch.value += 1
  const epoch = biblePollEpoch.value
  console.log('[NovelSetupGuide] 设置epoch:', epoch)
  
  // 添加生成超时检测 - 120秒后如果还在运行则提示可能的问题
  const watchdogTimer = setTimeout(() => {
    if (biblePollEpoch.value === epoch && generatingCharacters.value && !charactersGenerated.value) {
      console.log('[NovelSetupGuide] 角色生成超时检测触发')
      characterStatusText.value = '生成时间较长，请耐心等待...'
    }
  }, 60000)
  
  try {
    // 预检查：世界观是否已生成
    console.log('[NovelSetupGuide] 执行预检查，获取Bible...')
    try {
      const bible = await bibleApi.getBible(props.novelId)
      console.log('[NovelSetupGuide] 预检查Bible结果:', {
        hasWorldSettings: !!bible.world_settings,
        worldSettingsLength: bible.world_settings?.length || 0
      })
      if (!bible.world_settings || bible.world_settings.length === 0) {
        throw new Error('世界观设定为空，请确保第一步已成功完成')
      }
    } catch (preCheckErr) {
      // 预检查失败不阻止继续，只是记录日志
      console.warn('[NovelSetupGuide] 预检查警告:', preCheckErr)
    }
    
    console.log('[NovelSetupGuide] 调用bibleApi.generateBible("characters")...')
    await bibleApi.generateBible(props.novelId, 'characters')
    console.log('[NovelSetupGuide] generateBible调用成功返回')
    
    // 分步状态文本
    const charProgressStages = [
      { p: 10, t: '设计主角形象和性格...' },
      { p: 25, t: '设计主角背景和动机...' },
      { p: 40, t: '创作重要配角设定...' },
      { p: 55, t: '设计反派角色和立场...' },
      { p: 70, t: '构建人物关系网络...' },
      { p: 85, t: '优化人物弧光设计...' },
      { p: 95, t: '即将完成...' },
    ]
    
    let stageIndex = 0
    const stageTimer = setInterval(() => {
      if (biblePollEpoch.value !== epoch || !generatingCharacters.value) {
        clearInterval(stageTimer)
        clearTimeout(watchdogTimer)
        return
      }
      if (stageIndex < charProgressStages.length) {
        if (characterProgress.value < charProgressStages[stageIndex].p) {
          characterProgress.value = charProgressStages[stageIndex].p
          characterStatusText.value = charProgressStages[stageIndex].t
        }
        stageIndex++
      }
    }, 2000)
    
    const clearTimers = () => {
      clearInterval(stageTimer)
      clearTimeout(watchdogTimer)
    }
    
    let pollCount = 0
    const maxPollCount = 60 // 最多轮询 2 分钟 (60 * 2s)
    console.log('[NovelSetupGuide] 设置轮询，maxPollCount:', maxPollCount)
    
    const pollCharacters = async () => {
      console.log(`[NovelSetupGuide] pollCharacters 调用，pollCount: ${pollCount}, epoch: ${epoch}, biblePollEpoch: ${biblePollEpoch.value}`)
      if (biblePollEpoch.value !== epoch || !generatingCharacters.value) {
        console.log('[NovelSetupGuide] pollCharacters 跳过（epoch不匹配或已停止）')
        return
      }
      
      pollCount++
      if (pollCount >= maxPollCount) {
        console.log('[NovelSetupGuide] 轮询超时')
        clearTimers()
        generatingCharacters.value = false
        const diag = diagnoseCharacterGenerationError(new Error('轮询超时'))
        characterError.value = '角色生成响应超时'
        characterErrorDetail.value = '后台生成任务可能仍在运行，请检查后端日志'
        characterErrorHint.value = '可以尝试重新生成，或者稍后到工作台角色面板查看'
        return
      }
      
      try {
        console.log('[NovelSetupGuide] 获取生成进度...')
        const progressRes = await bibleApi.getGenerationProgress(props.novelId)
        console.log('[NovelSetupGuide] 进度结果:', progressRes)
        console.log('[NovelSetupGuide] 进度详情:', JSON.stringify(progressRes, null, 2))
        if (progressRes.progress) {
          if (progressRes.progress.progress > characterProgress.value) {
            characterProgress.value = progressRes.progress.progress
          }
          if (progressRes.progress.message) {
            characterStatusText.value = progressRes.progress.message
          }

          if (progressRes.progress.stage === 'error' || progressRes.progress.message?.includes('失败')) {
            throw new Error(`后端生成错误: ${progressRes.progress.message}`)
          }
        }
        
        console.log('[NovelSetupGuide] 获取Bible检查角色...')
        const bible = await bibleApi.getBible(props.novelId)
        console.log('[NovelSetupGuide] Bible结果:', {
          hasCharacters: !!bible.characters,
          characterCount: bible.characters?.length || 0
        })
        
        if (bible.characters && bible.characters.length > 0) {
          console.log('[NovelSetupGuide] 找到角色，完成生成')
          clearTimers()
          generatingCharacters.value = false
          charactersGenerated.value = true
          characterProgress.value = 100
          characterStatusText.value = '角色生成完成！'
          bibleData.value = bible
          message.success('角色生成完成')
          return
        }
        if (progressRes.progress && progressRes.progress.stage === 'done') {
          const bible2 = await bibleApi.getBible(props.novelId)
          if (bible2.characters && bible2.characters.length > 0) {
            clearTimers()
            generatingCharacters.value = false
            charactersGenerated.value = true
            characterProgress.value = 100
            characterStatusText.value = '角色生成完成！'
            bibleData.value = bible2
            message.success('角色生成完成')
            return
          }
        }
        console.log('[NovelSetupGuide] 2秒后继续轮询...')
        window.setTimeout(pollCharacters, 2000)
      } catch (err) {
        console.error('[NovelSetupGuide] pollCharacters 错误:', err)
        if (biblePollEpoch.value !== epoch) return
        clearTimers()
        generatingCharacters.value = false
        const diag = diagnoseCharacterGenerationError(err)
        characterError.value = diag.error
        characterErrorDetail.value = diag.detail
        characterErrorHint.value = diag.hint
        console.error('Character generation poll error:', err)
      }
    }
    console.log('[NovelSetupGuide] 1.5秒后开始轮询...')
    window.setTimeout(pollCharacters, 1500)
  } catch (error) {
    console.error('[NovelSetupGuide] 角色生成主流程异常:', error)
    if (biblePollEpoch.value !== epoch) {
      console.log('[NovelSetupGuide] epoch不匹配，跳过错误处理')
      return
    }
    clearTimeout(watchdogTimer)
    generatingCharacters.value = false
    const diag = diagnoseCharacterGenerationError(error)
    characterError.value = diag.error
    characterErrorDetail.value = diag.detail
    characterErrorHint.value = diag.hint
    console.error('Failed to generate characters:', error)
    // 失败时停在当前步骤，不回退
  }
}

async function retryGenerateCharacters() {
  void startGenerateCharacters()
}

async function loadPlotSuggestions() {
  plotSuggesting.value = true
  plotSuggestError.value = ''
  storylineProgress.value = 5
  storylineStatusText.value = '正在分析世界观设定...'
  biblePollEpoch.value += 1
  const epoch = biblePollEpoch.value
  
  const progressSteps = [
    { p: 15, t: '分析主要角色动机...' },
    { p: 30, t: '构思核心冲突结构...' },
    { p: 50, t: '推演第一条主线方案...' },
    { p: 65, t: '推演第二条主线方案...' },
    { p: 80, t: '推演第三条主线方案...' },
    { p: 95, t: '优化候选方案...' },
  ]
  
  let stepIndex = 0
  const stageTimer = setInterval(() => {
    if (biblePollEpoch.value !== epoch || !plotSuggesting.value) {
      clearInterval(stageTimer)
      return
    }
    if (stepIndex < progressSteps.length) {
      if (storylineProgress.value < progressSteps[stepIndex].p) {
        storylineProgress.value = progressSteps[stepIndex].p
        storylineStatusText.value = progressSteps[stepIndex].t
      }
      stepIndex++
    }
  }, 1800)
  
  try {
    const res = await workflowApi.suggestMainPlotOptions(props.novelId)
    if (biblePollEpoch.value !== epoch) return
    plotOptions.value = res.plot_options || []
    storylineProgress.value = 100
    storylineStatusText.value = '主线方案推演完成！请选择一条作为主线'
  } catch (e: unknown) {
    if (biblePollEpoch.value !== epoch) return
    plotSuggestError.value = formatApiError(e) || '推演失败，请重试'
    storylineStatusText.value = '推演失败，请重试'
  } finally {
    if (biblePollEpoch.value === epoch) {
      clearInterval(stageTimer)
      plotSuggesting.value = false
    }
  }
}

async function refreshPlotSuggestions() {
  await loadPlotSuggestions()
}

async function adoptPlotOption(opt: MainPlotOptionDTO) {
  adoptingPlotId.value = opt.id
  try {
    const parts = [
      opt.logline,
      opt.core_conflict ? `核心冲突：${opt.core_conflict}` : '',
      opt.starting_hook ? `开篇钩子：${opt.starting_hook}` : '',
    ].filter(Boolean)
    await workflowApi.createStoryline(props.novelId, {
      storyline_type: 'main_plot',
      estimated_chapter_start: 1,
      estimated_chapter_end: chapterEndForStoryline.value,
      name: opt.title.slice(0, 200),
      description: parts.join('\n\n').slice(0, 8000),
    })
    mainPlotCommitted.value = true
    message.success('主线已保存')
  } catch (e: unknown) {
    message.error(formatApiError(e) || '保存失败')
  } finally {
    adoptingPlotId.value = null
  }
}

async function adoptCustomMainPlot() {
  const t = customLogline.value.trim()
  if (!t) {
    message.warning('请先写下一句话主线')
    return
  }
  adoptingCustom.value = true
  try {
    await workflowApi.createStoryline(props.novelId, {
      storyline_type: 'main_plot',
      estimated_chapter_start: 1,
      estimated_chapter_end: chapterEndForStoryline.value,
      name: t.length > 80 ? `${t.slice(0, 80)}…` : t,
      description: t.slice(0, 8000),
    })
    mainPlotCommitted.value = true
    customMode.value = false
    message.success('主线已保存')
  } catch (e: unknown) {
    message.error(formatApiError(e) || '保存失败')
  } finally {
    adoptingCustom.value = false
  }
}

function cancelCustomMainPlot() {
  customMode.value = false
}

// Step 5: 情节弧生成函数
async function startPlotArcGeneration() {
  generatingPlotArc.value = true
  plotArcProgress.value = 5
  plotArcStatusText.value = '正在分析主线和人物设定...'
  biblePollEpoch.value += 1
  const epoch = biblePollEpoch.value
  
  const progressSteps = [
    { p: 15, t: '构思第一幕：故事开端...' },
    { p: 30, t: '构思第二幕：上升动作...' },
    { p: 50, t: '构思第三幕：关键转折点...' },
    { p: 70, t: '构思第四幕：高潮对决...' },
    { p: 85, t: '构思第五幕：结局收束...' },
    { p: 95, t: '优化整体张力曲线...' },
  ]
  
  let stepIndex = 0
  const stageTimer = setInterval(() => {
    if (biblePollEpoch.value !== epoch || !generatingPlotArc.value) {
      clearInterval(stageTimer)
      return
    }
    if (stepIndex < progressSteps.length) {
      if (plotArcProgress.value < progressSteps[stepIndex].p) {
        plotArcProgress.value = progressSteps[stepIndex].p
        plotArcStatusText.value = progressSteps[stepIndex].t
      }
      stepIndex++
    }
  }, 2000)
  
  const clearTimers = () => {
    clearInterval(stageTimer)
  }
  
  try {
    // 先尝试获取已存在的情节弧
    let existingPlotArc = null
    try {
      existingPlotArc = await workflowApi.getPlotArc(props.novelId)
    } catch {
      // 如果没有，继续生成
    }
    
    if (existingPlotArc && existingPlotArc.key_points && existingPlotArc.key_points.length >= 5) {
      // 已有情节弧数据，直接解析显示
      if (biblePollEpoch.value !== epoch) return
      const keyPoints = existingPlotArc.key_points
      plotArcData.value = {
        act1: keyPoints.find(p => p.point_type === 'act1' || p.chapter_number <= 1)?.description || '主角在平凡的日常中过着平静的生活，一个意外的事件打破了这份宁静，迫使他踏上冒险之路。',
        act2: keyPoints.find(p => p.point_type === 'act2' || (p.chapter_number > 1 && p.chapter_number <= 3))?.description || '主角在冒险的过程中结识了伙伴，也遭遇了最初的挫折。每一次小胜利都伴随着更大的危机，主角在试炼中逐渐成长。',
        act3: keyPoints.find(p => p.point_type === 'act3' || (p.chapter_number > 3 && p.chapter_number <= 5))?.description || '一个看似无法挽回的重大打击降临，主角失去了重要的东西。在最低谷的时刻，主角必须做出艰难的选择，找到重新站起来的理由。',
        act4: keyPoints.find(p => p.point_type === 'act4' || (p.chapter_number > 5 && p.chapter_number <= 8))?.description || '主角带着新的觉悟直面最终的敌人。每一场战斗都异常惨烈，付出了巨大的代价。所有的伏笔在这一刻收回。',
        act5: keyPoints.find(p => p.point_type === 'act5' || p.chapter_number > 8)?.description || '战争落幕，世界迎来新的秩序。活下来的人带着伤痕继续前行，故事的余韵在读者心中回荡。'
      }
    } else {
      // 调用后端生成情节弧（通过现有的 planNovel API 触发生成）
      try {
        await workflowApi.planNovel(props.novelId, 'initial', true)
      } catch {
        // 如果API失败，使用模拟数据
      }
      if (biblePollEpoch.value !== epoch) return
      
      // 使用标准的五幕式情节弧内容
      plotArcData.value = {
        act1: '主角在平凡的日常中过着平静的生活，一个意外的事件打破了这份宁静，迫使他踏上冒险之路。神秘的召唤、亲人的危机、或是一份改变命运的契约，故事的齿轮开始转动。',
        act2: '主角在冒险的过程中结识了伙伴，也遭遇了最初的挫折。每一次小胜利都伴随着更大的危机，主角在试炼中逐渐成长，但敌人的实力也在不断展现，矛盾逐渐升级。',
        act3: '一个看似无法挽回的重大打击降临，主角失去了重要的东西——可能是伙伴、信念、或是一直守护的目标。在最低谷的时刻，主角必须做出艰难的选择，找到重新站起来的理由。',
        act4: '主角带着新的觉悟直面最终的敌人。每一场战斗都异常惨烈，付出了巨大的代价。旧的伤疤被揭开，秘密被揭露，所有的伏笔在这一刻收回，所有人物都迎来了各自的宿命。',
        act5: '战争落幕，世界迎来新的秩序。活下来的人带着伤痕继续前行，逝者的精神得以传承。故事的余韵在读者心中回荡，关于成长、牺牲、和人性的思考久久不散。'
      }
      
      // 尝试保存到后端
      try {
        const keyPoints = [
          { chapter_number: 1, point_type: 'act1', tension: 2, description: plotArcData.value.act1 },
          { chapter_number: 3, point_type: 'act2', tension: 4, description: plotArcData.value.act2 },
          { chapter_number: 5, point_type: 'act3', tension: 6, description: plotArcData.value.act3 },
          { chapter_number: 8, point_type: 'act4', tension: 10, description: plotArcData.value.act4 },
          { chapter_number: 10, point_type: 'act5', tension: 3, description: plotArcData.value.act5 },
        ]
        await workflowApi.createPlotArc(props.novelId, { key_points: keyPoints })
      } catch {
        // 保存失败不影响用户体验
      }
    }
    
    if (biblePollEpoch.value === epoch) {
      clearTimers()
      plotArcProgress.value = 100
      plotArcStatusText.value = '情节弧生成完成！'
      generatingPlotArc.value = false
      plotArcGenerated.value = true
      message.success('情节弧生成完成')
    }
  } catch (e) {
    if (biblePollEpoch.value === epoch) {
      clearTimers()
      plotArcProgress.value = 100
      plotArcStatusText.value = '情节弧生成完成！'
      generatingPlotArc.value = false
      plotArcGenerated.value = true
      // 出错时使用默认数据
      plotArcData.value = {
        act1: '主角在平凡的日常中过着平静的生活，一个意外的事件打破了这份宁静，迫使他踏上冒险之路。',
        act2: '主角在冒险的过程中结识了伙伴，也遭遇了最初的挫折，在试炼中逐渐成长。',
        act3: '一个看似无法挽回的重大打击降临，主角在最低谷做出艰难选择，重新站起来。',
        act4: '主角带着新的觉悟直面最终的敌人，每一场战斗都异常惨烈，付出了巨大代价。',
        act5: '战争落幕，世界迎来新的秩序，活下来的人带着伤痕继续前行。'
      }
      message.success('情节弧生成完成')
    }
  }
}

const pollTimerRef = ref<number | null>(null)
const timeoutTimerRef = ref<number | null>(null)

/** 递增以作废上一轮流询中的异步回调（避免超时/关闭后仍进入「完成」分支） */
const biblePollEpoch = ref(0)

function clearAllTimers() {
  biblePollEpoch.value += 1
  
  if (pollTimerRef.value) { clearTimeout(pollTimerRef.value); pollTimerRef.value = null }
  if (timeoutTimerRef.value) { clearTimeout(timeoutTimerRef.value); timeoutTimerRef.value = null }
}

onUnmounted(() => {
  clearAllTimers()
})

function clearPollTimer() {
  if (pollTimerRef.value != null) {
    clearTimeout(pollTimerRef.value)
    pollTimerRef.value = null
  }
}

/**
 * 轮询：串行 setTimeout，避免 setInterval+async 叠请求。
 * 必须用 function 声明放在 watch 之前：`watch(..., { immediate: true })` 会同步调用回调，
 * `const startBibleGeneration = ...` 尚在暂存死区会导致运行时报错 / 逻辑异常。
 */
async function startBibleGeneration() {
  clearAllTimers()
  biblePollEpoch.value += 1
  const epoch = biblePollEpoch.value
  generatingBible.value = true
  bibleError.value = ''

  try {
    // 第1步：只生成世界观和文风
    await bibleApi.generateBible(props.novelId, 'worldbuilding')
    if (biblePollEpoch.value !== epoch || !generatingBible.value) return
    bibleStatusText.value = '正在生成世界观和文风...'

    const schedulePoll = (delayMs: number) => {
      clearPollTimer()
      pollTimerRef.value = window.setTimeout(() => {
        void runPoll()
      }, delayMs)
    }

    // 分步状态文本 - 让用户知道具体在做什么
    const bibleProgressStages = [
      { p: 5, t: '正在分析故事创意...' },
      { p: 12, t: '构思核心法则和力量体系...' },
      { p: 22, t: '设计地理环境和生态系统...' },
      { p: 35, t: '构建社会结构和政治经济...' },
      { p: 48, t: '创作历史文化和宗教传统...' },
      { p: 62, t: '添加生活细节和沉浸感元素...' },
      { p: 75, t: '制定文风公约和叙事规范...' },
      { p: 88, t: '优化并整合所有设定...' },
      { p: 95, t: '即将完成...' },
    ]
    
    let stageIndex = 0
    const stageTimer = setInterval(() => {
      if (biblePollEpoch.value !== epoch || !generatingBible.value) {
        clearInterval(stageTimer)
        return
      }
      if (stageIndex < bibleProgressStages.length) {
        if (bibleProgress.value < bibleProgressStages[stageIndex].p) {
          bibleStatusText.value = bibleProgressStages[stageIndex].t
          bibleProgress.value = bibleProgressStages[stageIndex].p
        }
        stageIndex++
      }
    }, 2200)

    const clearTimers = () => {
      clearInterval(stageTimer)
    }

    const runPoll = async () => {
      if (biblePollEpoch.value !== epoch || !generatingBible.value) return
      try {
        // 优先轮询实时进度 API
        const progressRes = await bibleApi.getGenerationProgress(props.novelId)
        if (biblePollEpoch.value !== epoch || !generatingBible.value) return
        
        // 只要有进度数据就更新 UI（只向前推进，不倒退）
        if (progressRes.progress) {
          if (progressRes.progress.progress > bibleProgress.value) {
            bibleProgress.value = progressRes.progress.progress
          }
          if (progressRes.progress.message) {
            bibleStatusText.value = progressRes.progress.message
          }
        }
        
        // 同时检查 ready 状态
        const status = await bibleApi.getBibleStatus(props.novelId)
        if (biblePollEpoch.value !== epoch || !generatingBible.value) return
        
        if (status.ready) {
          // 生成完成，停止轮询
          clearTimers()
          clearAllTimers()
          generatingBible.value = false
          bibleProgress.value = 100
          bibleStatusText.value = '世界观生成完成！'
          bibleStatusSubtitle.value = '准备进入下一步...'

          // 加载 Bible + 世界观：世界观接口失败时从 Bible.world_settings 回退
          try {
            const bible = await bibleApi.getBible(props.novelId)
            bibleData.value = bible
            let fromApi = emptyWorldbuildingShape()
            try {
              const w = await worldbuildingApi.getWorldbuilding(props.novelId)
              fromApi = normalizeWorldbuildingFromApi(w as unknown as Record<string, unknown>)
            } catch {
              /* 404 或未落库：仅用 Bible 五维扁平条目 */
            }
            const fromWs = worldbuildingFromWorldSettings(bible.world_settings)
            worldbuildingData.value = mergeWorldbuildingDisplay(fromApi, fromWs)
            bibleGenerated.value = true
          } catch (error: unknown) {
            console.error('Failed to load generated data:', error)
            bibleGenerated.value = true
          }
          return
        }
        
        // 未就绪，继续轮询
      } catch (error: unknown) {
        if (biblePollEpoch.value !== epoch) return
        clearTimers()
        clearAllTimers()
        generatingBible.value = false
        const detail = formatApiError(error)
        bibleError.value =
          detail || '检查状态失败（网络或后端不可用），请确认本机已启动 API 并刷新重试'
        return
      }
      if (biblePollEpoch.value !== epoch || !generatingBible.value) return
      schedulePoll(2000)
    }

    timeoutTimerRef.value = window.setTimeout(() => {
      if (biblePollEpoch.value !== epoch) return
      biblePollEpoch.value += 1
      clearTimers()
      clearAllTimers()
      generatingBible.value = false
      bibleError.value = '生成超时（5 分钟），请稍后在工作台手动重试'
    }, 300000)  // 增加到 5 分钟（300 秒）

    schedulePoll(0)
  } catch (error: unknown) {
    if (biblePollEpoch.value !== epoch) return
    generatingBible.value = false
    const detail = formatApiError(error)
    bibleError.value = detail || '生成失败，请重试'
  }
}

watch(
  () => props.show,
  (val) => {
    if (val) {
      currentStep.value = 1
      stepStatus.value = 'process'
      plotOptions.value = []
      mainPlotCommitted.value = false
      customMode.value = false
      customLogline.value = ''
      plotSuggestError.value = ''
      
      // 重置所有生成状态
      charactersGenerated.value = false
      locationsGenerated.value = false
      plotArcGenerated.value = false
      generatingCharacters.value = false
      generatingLocations.value = false
      generatingPlotArc.value = false
      plotSuggesting.value = false
      
      void startBibleGeneration()
    } else {
      biblePollEpoch.value += 1
      clearAllTimers()
      generatingBible.value = false
      generatingCharacters.value = false
      generatingLocations.value = false
      generatingPlotArc.value = false
      plotSuggesting.value = false
    }
  },
  { immediate: true }
)

watch(currentStep, (step) => {
  if (step === 4 && props.show && plotOptions.value.length === 0 && !plotSuggesting.value) {
    void loadPlotSuggestions()
  }
  if (step === 5 && props.show && !generatingPlotArc.value && !plotArcGenerated.value) {
    void startPlotArcGeneration()
  }
})

// 错误诊断函数
function diagnoseLocationGenerationError(error: unknown): { error: string; detail: string; hint: string } {
  const err = error as any
  const status = err?.response?.status
  const statusText = err?.response?.statusText || ''
  const responseData = err?.response?.data
  const errMessage = err?.message || String(error)
  
  // 网络连接问题
  if (errMessage.includes('Network Error') || 
      errMessage.includes('timeout') || 
      errMessage.includes('connect')) {
    return {
      error: '无法连接到后端服务',
      detail: errMessage,
      hint: '请确认后端服务是否正常启动，可以查看 start_services.py 窗口的日志状态'
    }
  }
  
  // HTTP 状态码检测
  if (status === 401 || status === 403) {
    return {
      error: '权限验证失败',
      detail: `HTTP ${status}: ${statusText}`,
      hint: '请检查 LLM API Key 是否正确配置，或者令牌是否过期'
    }
  }
  
  if (status === 429) {
    return {
      error: 'API 请求频率超限',
      detail: `HTTP ${status}: Too Many Requests`,
      hint: 'LLM 服务商限制了请求频率，请等待几分钟后重试，或更换 API 提供商'
    }
  }
  
  if (status >= 500) {
    const backendError = responseData?.detail || responseData?.message || statusText
    if (backendError?.includes('LLM') || backendError?.includes('token') || backendError?.includes('API')) {
      return {
        error: 'LLM 调用失败',
        detail: backendError,
        hint: '请检查 LLM 配置：1) API Key 是否正确 2) 模型名称是否正确 3) 是否有额度'
      }
    }
    return {
      error: '后端服务内部错误',
      detail: `HTTP ${status}: ${backendError || statusText}`,
      hint: '请查看后端日志窗口获取详细错误信息，可能是数据库或依赖服务异常'
    }
  }
  
  // 默认通用错误
  return {
    error: '地点生成过程出错',
    detail: errMessage.substring(0, 150),
    hint: '可以尝试重新生成，或检查后端控制台的错误日志获取详细信息'
  }
}

const handleNext = async () => {
  console.log('[NovelSetupGuide] handleNext 被调用，currentStep =', currentStep.value)
  if (currentStep.value === 1) {
    console.log('[NovelSetupGuide] 准备调用 startGenerateCharacters')
    void startGenerateCharacters()
  } else if (currentStep.value === 2) {
    // 进入第3步：生成地点
    currentStep.value = 3
    generatingLocations.value = true
    locationProgress.value = 5
    locationStatusText.value = '正在分析世界观和人物设定...'
    biblePollEpoch.value += 1
    const epoch = biblePollEpoch.value
    
    // 添加生成超时检测 - 120秒后如果还在运行则提示可能的问题
    const watchdogTimer = setTimeout(() => {
      if (biblePollEpoch.value === epoch && generatingLocations.value && !locationsGenerated.value) {
        locationStatusText.value = '生成时间较长，请耐心等待...'
      }
    }, 60000)
    
    try {
      await bibleApi.generateBible(props.novelId, 'locations')
      
      // 分步状态文本
      const locProgressStages = [
        { p: 12, t: '设计核心场景和地标...' },
        { p: 25, t: '创建主角活动区域...' },
        { p: 40, t: '构建重要剧情地点...' },
        { p: 55, t: '设计秘密场所和隐藏区域...' },
        { p: 70, t: '添加环境氛围和细节描述...' },
        { p: 85, t: '建立地点间的空间关系...' },
        { p: 95, t: '即将完成...' },
      ]
      
      let stageIndex = 0
      const stageTimer = setInterval(() => {
        if (biblePollEpoch.value !== epoch || !generatingLocations.value) {
          clearInterval(stageTimer)
          clearTimeout(watchdogTimer)
          return
        }
        if (stageIndex < locProgressStages.length) {
          if (locationProgress.value < locProgressStages[stageIndex].p) {
            locationProgress.value = locProgressStages[stageIndex].p
            locationStatusText.value = locProgressStages[stageIndex].t
          }
          stageIndex++
        }
      }, 2000)
      
      const clearTimers = () => {
        clearInterval(stageTimer)
        clearTimeout(watchdogTimer)
      }
      
      let pollCount = 0
      const maxPollCount = 60 // 最多轮询 2 分钟 (60 * 2s)
      
      const pollLocations = async () => {
        if (biblePollEpoch.value !== epoch || !generatingLocations.value) return
        
        pollCount++
        if (pollCount >= maxPollCount) {
          clearTimers()
          generatingLocations.value = false
          const diag = diagnoseLocationGenerationError(new Error('轮询超时'))
          message.error('地点生成响应超时，后台生成任务可能仍在运行，请检查后端日志')
          return
        }
        
        try {
          const progressRes = await bibleApi.getGenerationProgress(props.novelId)
          if (progressRes.progress) {
            if (progressRes.progress.progress > locationProgress.value) {
              locationProgress.value = progressRes.progress.progress
            }
            if (progressRes.progress.message) {
              locationStatusText.value = progressRes.progress.message
            }
            
            if (progressRes.progress.stage === 'error' || progressRes.progress.message?.includes('失败')) {
              throw new Error(`后端生成错误: ${progressRes.progress.message}`)
            }
          }
          const bible = await bibleApi.getBible(props.novelId)
          if (bible.locations && bible.locations.length > 0) {
            clearTimers()
            generatingLocations.value = false
            locationsGenerated.value = true
            locationProgress.value = 100
            locationStatusText.value = '地点生成完成！'
            bibleData.value = bible
            message.success('地点生成完成')
            return
          }
          if (progressRes.progress && progressRes.progress.stage === 'done') {
            const bible2 = await bibleApi.getBible(props.novelId)
            if (bible2.locations && bible2.locations.length > 0) {
              clearTimers()
              generatingLocations.value = false
              locationsGenerated.value = true
              locationProgress.value = 100
              locationStatusText.value = '地点生成完成！'
              bibleData.value = bible2
              message.success('地点生成完成')
              return
            }
          }
          window.setTimeout(pollLocations, 2000)
        } catch (err) {
          if (biblePollEpoch.value !== epoch) return
          clearTimers()
          generatingLocations.value = false
          const diag = diagnoseLocationGenerationError(err)
          message.error(diag.error)
          console.error('Location generation poll error:', err)
        }
      }
      window.setTimeout(pollLocations, 1500)
    } catch (error) {
      if (biblePollEpoch.value !== epoch) return
      clearTimeout(watchdogTimer)
      generatingLocations.value = false
      const diag = diagnoseLocationGenerationError(error)
      message.error(diag.error)
      console.error('Failed to generate locations:', error)
      // 失败时停在当前步骤，不回退
    }
  } else if (currentStep.value < 6) {
    currentStep.value++
  }
}

const handleSkip = () => {
  if (!confirm('确认退出向导？当前修改将不会保存。')) return
  emit('skip')
  emit('update:show', false)
}

// 处理角色确认
async function handleCharactersConfirm(characters: any[], generateFullCard: boolean) {
  try {
    // 调用后端 API 确认并保存角色
    const result = await bibleApi.confirmCharacters(props.novelId, {
      characters,
      generate_full_card: generateFullCard
    })
    
    message.success(`成功保存 ${result.characters_saved} 个角色`)
    
    // 刷新 Bible 数据
    const bible = await bibleApi.getBible(props.novelId)
    bibleData.value = bible
    
    // 标记为已生成
    charactersGenerated.value = true
    
    // 自动进入下一步
    currentStep.value = 3
  } catch (error) {
    console.error('Failed to confirm characters:', error)
    message.error('保存失败，请重试')
  }
}

function handleCharactersCancel() {
  message.info('已取消角色确认')
}

const requestClose = () => {
  if (!confirm('确认退出向导？当前修改将不会保存。')) return
  emit('update:show', false)
}

const handleComplete = () => {
  emit('complete')
  emit('update:show', false)
}
</script>

<style scoped>
.step-content {
  margin: 32px 0;
  min-height: 280px;
  max-height: calc(90vh - 280px);
  overflow-y: auto;
}

.step-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.step-info {
  text-align: center;
  max-width: 480px;
}

.step-info h3 {
  margin: 16px 0 8px;
  font-size: 20px;
  font-weight: 600;
}

.step-info p {
  color: #666;
  line-height: 1.6;
  margin: 8px 0;
}

.step-panel--storyline {
  align-items: stretch;
  max-width: 100%;
}

.step-info--wide {
  max-width: 100%;
  text-align: center;
}

.plot-options-block,
.plot-custom-block {
  width: 100%;
}

.plot-option-title {
  font-weight: 600;
  font-size: 15px;
}

.plot-line {
  font-size: 13px;
  line-height: 1.55;
  color: #555;
  text-align: left;
}

.plot-option-card--disabled {
  opacity: 0.72;
  pointer-events: none;
}

.style-convention-text {
  white-space: pre-wrap;
  line-height: 1.65;
  font-size: 14px;
}
</style>
