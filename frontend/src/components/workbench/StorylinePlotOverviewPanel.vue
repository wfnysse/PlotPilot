<template>
  <div class="spo-panel">
    <n-alert type="info" :show-icon="true" class="spo-intro" title="故事线 · 情节弧（全书骨架）">
      <ul class="spo-bullets">
        <li><strong>写</strong>：宏观规划（MACRO_PLANNING）或重大转折后人工调整故事线起止章；情节弧关键张力点在此维护。</li>
        <li><strong>读</strong>：幕/章规划（ACT_PLANNING）与生成上下文组装时注入「当前处于哪条线、弧上张力位置」。</li>
      </ul>
    </n-alert>

    <n-spin :show="loading" class="spo-spin">
      <n-space vertical :size="14" style="width: 100%">
        <!-- 迷你甘特：故事线 -->
        <n-card title="故事线覆盖（章节轴示意）" size="small" :bordered="true">
          <template #header-extra>
            <n-text depth="3" style="font-size: 11px">横轴为章号，色条为线体跨度</n-text>
          </template>
          <n-empty v-if="storylines.length === 0" description="暂无故事线，展开下方「故事线列表」添加" />
          <div v-else class="gantt-wrap">
            <div class="gantt-axis">
              <span>1</span>
              <span v-if="maxChapter > 1">{{ midChapterLabel }}</span>
              <span>{{ maxChapter }}</span>
            </div>
            <div
              v-for="sl in storylines"
              :key="sl.id"
              class="gantt-row"
            >
              <div class="gantt-label" :title="sl.name || sl.id">
                <n-tag :type="typeColor(sl.storyline_type)" size="tiny" round>
                  {{ typeLabel(sl.storyline_type) }}
                </n-tag>
                <span class="gantt-name">{{ shortName(sl) }}</span>
              </div>
              <div class="gantt-track">
                <div
                  class="gantt-bar"
                  :style="barStyle(sl.estimated_chapter_start, sl.estimated_chapter_end)"
                />
              </div>
            </div>
          </div>
        </n-card>

        <!-- 张力曲线 -->
        <n-card title="情节弧 · 张力曲线" size="small" :bordered="true">
          <n-empty v-if="plotPoints.length === 0" description="暂无剧情点，展开下方「情节弧编辑」添加" />
          <div v-else class="chart-wrap">
            <svg viewBox="0 0 800 200" class="tension-svg">
              <line
                v-for="i in 4"
                :key="'g' + i"
                :x1="0"
                :y1="i * 50"
                :x2="800"
                :y2="i * 50"
                stroke="var(--n-border-color)"
                stroke-width="1"
                stroke-dasharray="4,4"
              />
              <polyline
                :points="tensionPolyline"
                fill="none"
                stroke="#18a058"
                stroke-width="3"
              />
              <g v-for="p in sortedPoints" :key="p.chapter_number">
                <circle
                  :cx="chapterX(p.chapter_number)"
                  :cy="tensionY(p.tension)"
                  r="6"
                  fill="#2080f0"
                  stroke="#fff"
                  stroke-width="2"
                />
                <text
                  :x="chapterX(p.chapter_number)"
                  :y="tensionY(p.tension) - 12"
                  text-anchor="middle"
                  font-size="11"
                  fill="var(--n-text-color-3)"
                >
                  Ch{{ p.chapter_number }}
                </text>
              </g>
            </svg>
          </div>
        </n-card>

        <n-collapse :default-expanded-names="['sl', 'pa']">
          <n-collapse-item title="故事线列表与编辑" name="sl">
            <StorylinePanel :slug="slug" />
          </n-collapse-item>
          <n-collapse-item title="情节弧（剧情点）编辑" name="pa">
            <PlotArcPanel :slug="slug" />
          </n-collapse-item>
        </n-collapse>
      </n-space>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkbenchRefreshStore } from '../../stores/workbenchRefreshStore'
import { workflowApi } from '../../api/workflow'
import type { StorylineDTO, PlotArcDTO, PlotPointDTO } from '../../api/workflow'
import StorylinePanel from './StorylinePanel.vue'
import PlotArcPanel from './PlotArcPanel.vue'

const props = defineProps<{ slug: string }>()

const loading = ref(false)
const storylines = ref<StorylineDTO[]>([])
const plotPoints = ref<PlotPointDTO[]>([])

const maxChapter = computed(() => {
  let m = 1
  for (const sl of storylines.value) {
    m = Math.max(m, sl.estimated_chapter_end || 1, sl.estimated_chapter_start || 1)
  }
  for (const p of plotPoints.value) {
    m = Math.max(m, p.chapter_number || 1)
  }
  return Math.max(m, 12)
})

const midChapterLabel = computed(() => String(Math.round(maxChapter.value / 2)))

const sortedPoints = computed(() =>
  [...plotPoints.value].sort((a, b) => a.chapter_number - b.chapter_number)
)

function chapterX(ch: number): number {
  const max = maxChapter.value
  if (max <= 1) return 400
  return 40 + ((ch - 1) / (max - 1)) * 720
}

function tensionY(t: number): number {
  const clamped = Math.min(4, Math.max(1, t))
  return 200 - (clamped - 1) * 45 - 10
}

const tensionPolyline = computed(() =>
  sortedPoints.value.map(p => `${chapterX(p.chapter_number)},${tensionY(p.tension)}`).join(' ')
)

function barStyle(start: number, end: number) {
  const max = maxChapter.value
  const s = Math.max(1, start)
  const e = Math.max(s, end)
  const leftPct = ((s - 1) / max) * 100
  const widthPct = ((e - s + 1) / max) * 100
  return {
    left: `${leftPct}%`,
    width: `${Math.min(100 - leftPct, widthPct)}%`,
  }
}

function typeLabel(t: string) {
  const map: Record<string, string> = {
    main_plot: '主线',
    romance: '感情',
    mystery: '悬疑',
    subplot: '支线',
  }
  return map[t] || t
}

function typeColor(t: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  if (t === 'main_plot') return 'success'
  if (t === 'romance') return 'error'
  if (t === 'mystery') return 'warning'
  return 'info'
}

function shortName(sl: StorylineDTO) {
  const n = (sl.name || '').trim()
  if (n) return n.length > 10 ? `${n.slice(0, 10)}…` : n
  return sl.id.slice(0, 8)
}

async function load() {
  loading.value = true
  try {
    const [sl, arc] = await Promise.all([
      workflowApi.getStorylines(props.slug),
      workflowApi.getPlotArc(props.slug).catch(() => null as PlotArcDTO | null),
    ])
    storylines.value = sl || []
    plotPoints.value = arc?.key_points ?? []
  } catch {
    storylines.value = []
    plotPoints.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.slug, () => void load(), { immediate: true })

const refreshStore = useWorkbenchRefreshStore()
const { deskTick } = storeToRefs(refreshStore)
watch(deskTick, () => void load())
</script>

<style scoped>
.spo-panel {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 12px 16px;
}

.spo-intro {
  margin-bottom: 12px;
}

.spo-bullets {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 12px;
  line-height: 1.55;
}

.spo-spin {
  width: 100%;
}

.gantt-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gantt-axis {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--n-text-color-3);
  padding: 0 4px 4px;
}

.gantt-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
}

.gantt-label {
  width: 120px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.gantt-name {
  font-size: 11px;
  color: var(--n-text-color-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gantt-track {
  flex: 1;
  height: 14px;
  background: var(--n-color-hover);
  border-radius: 7px;
  position: relative;
  min-width: 0;
}

.gantt-bar {
  position: absolute;
  top: 2px;
  height: 10px;
  border-radius: 5px;
  background: linear-gradient(90deg, #36ad6a, #18a058);
  min-width: 4px;
}

.chart-wrap {
  width: 100%;
  overflow-x: auto;
}

.tension-svg {
  width: 100%;
  max-width: 800px;
  height: auto;
  display: block;
}

.spo-panel :deep(.storyline-panel),
.spo-panel :deep(.plot-arc-panel) {
  background: transparent;
}

.spo-panel :deep(.storyline-panel .panel-header),
.spo-panel :deep(.plot-arc-panel .panel-header) {
  padding-top: 0;
}
</style>
