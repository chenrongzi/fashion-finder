const API = '';  // 同域，不用写前缀

// ── 状态映射 ─────────────────────────────────────────────
const STATUS_MAP = {
  pending:  { label: '待审核',     cls: 'status-pending'  },
  sent:     { label: '已发老板娘', cls: 'status-sent'     },
  approved: { label: '通过 ✅',   cls: 'status-approved' },
  rejected: { label: '拒绝 ❌',   cls: 'status-rejected' },
};

// ── 全局状态 ─────────────────────────────────────────────
let galleryOffset = 0;
let galleryStatus = '';
let galleryTotal  = 0;
let currentModal  = null;  // 当前详情弹窗的图片 id

// ── Tab 切换 ─────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab, .tab-content').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'gallery') loadGallery(true);
  });
});

// ── 统计栏 ────────────────────────────────────────────────
async function loadStats() {
  const [all, sent, approved] = await Promise.all([
    fetch(`${API}/api/images?limit=1`).then(r => r.json()),
    fetch(`${API}/api/images?status=sent&limit=1`).then(r => r.json()),
    fetch(`${API}/api/images?status=approved&limit=1`).then(r => r.json()),
  ]);
  document.getElementById('statsBar').textContent =
    `共 ${all.total} 张  |  待审 ${sent.total}  |  过审 ${approved.total}`;
}
loadStats();

// ── 批量进度 ─────────────────────────────────────────────
let batchDurations = [];

function startBatch(total) {
  batchDurations = [];
  const area = document.getElementById('progressArea');
  area.classList.remove('hidden');
  document.getElementById('progressFill').style.width = '0%';
  updateProgress(0, total);
}

function updateProgress(done, total) {
  const pct = total > 0 ? (done / total * 100).toFixed(1) : 0;
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressText').textContent = `正在分析 ${done} / ${total} 张`;

  const remaining = total - done;
  const etaEl = document.getElementById('progressEta');
  if (done === total) {
    etaEl.textContent = '✅ 全部完成';
    setTimeout(() => document.getElementById('progressArea').classList.add('hidden'), 2500);
  } else if (batchDurations.length > 0) {
    const avg = batchDurations.reduce((a, b) => a + b, 0) / batchDurations.length;
    etaEl.textContent = '预计还需 ' + fmtMs(avg * remaining);
  } else {
    etaEl.textContent = '计算中...';
  }
}

function fmtMs(ms) {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} 秒`;
  const m = Math.floor(s / 60), ss = s % 60;
  return ss > 0 ? `${m} 分 ${ss} 秒` : `${m} 分钟`;
}

// ── 上传：点击区域 ────────────────────────────────────────
const uploadZone  = document.getElementById('uploadZone');
const fileInput   = document.getElementById('fileInput');
const uploadQueue = document.getElementById('uploadQueue');

uploadZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async () => {
  const files = Array.from(fileInput.files);
  fileInput.value = '';
  if (files.length >= 2) startBatch(files.length);
  let done = 0;
  for (const file of files) {
    const t0 = Date.now();
    await uploadFile(file);
    done++;
    if (files.length >= 2) {
      batchDurations.push(Date.now() - t0);
      updateProgress(done, files.length);
    }
  }
  loadStats();
});

// 拖放
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.style.background = '#fce8ec'; });
uploadZone.addEventListener('dragleave', () => { uploadZone.style.background = ''; });
uploadZone.addEventListener('drop', async e => {
  e.preventDefault();
  uploadZone.style.background = '';
  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
  if (files.length >= 2) startBatch(files.length);
  let done = 0;
  for (const file of files) {
    const t0 = Date.now();
    await uploadFile(file);
    done++;
    if (files.length >= 2) {
      batchDurations.push(Date.now() - t0);
      updateProgress(done, files.length);
    }
  }
  loadStats();
});

async function uploadFile(file) {
  const platform = document.getElementById('platformSelect').value;
  const itemEl = addQueueItem(file.name, URL.createObjectURL(file));

  const fd = new FormData();
  fd.append('file', file);
  fd.append('platform', platform);

  try {
    const res = await fetch(`${API}/api/images/upload`, { method: 'POST', body: fd });
    const data = await res.json();
    setQueueStatus(itemEl, 'done', '✅ 分析完成');
    showAnalysis(data, URL.createObjectURL(file));
    if (data.image) prependToGallery(data.image);
  } catch (e) {
    setQueueStatus(itemEl, 'error', '❌ 上传失败：' + e.message);
  }
}

// ── URL 抓取 ──────────────────────────────────────────────
document.getElementById('fetchBtn').addEventListener('click', async () => {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) return alert('请输入图片链接');
  const platform = document.getElementById('platformSelect').value;
  const itemEl = addQueueItem(url.slice(0, 40) + '…', null);

  try {
    const res = await fetch(`${API}/api/images/fetch-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, platform }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '未知错误');
    setQueueStatus(itemEl, 'done', '✅ 分析完成');
    showAnalysis(data, `/uploads/${data.filename}`);
    if (data.image) prependToGallery(data.image);
    document.getElementById('urlInput').value = '';
    loadStats();
  } catch (e) {
    setQueueStatus(itemEl, 'error', '❌ 失败：' + e.message);
  }
});

// ── 队列 UI ───────────────────────────────────────────────
function addQueueItem(name, thumbSrc) {
  const el = document.createElement('div');
  el.className = 'queue-item';
  el.innerHTML = `
    <img class="queue-thumb" src="${thumbSrc || ''}" alt="">
    <div class="queue-info">
      <div class="queue-name">${escHtml(name)}</div>
      <div class="queue-status">AI 分析中...</div>
    </div>`;
  uploadQueue.prepend(el);
  return el;
}
function setQueueStatus(el, cls, text) {
  const s = el.querySelector('.queue-status');
  s.className = 'queue-status ' + cls;
  s.textContent = text;
}

// ── 分析结果展示 ─────────────────────────────────────────
function showAnalysis(data, imgSrc) {
  const a = data.analysis || {};
  const card = document.getElementById('analysisResult');
  card.classList.remove('hidden');
  card.innerHTML = `
    <img src="${imgSrc}" alt="">
    <div class="ai-style">${escHtml(a.style || '—')}</div>
    <div class="ai-meta">${escHtml(a.category || '')}  ${escHtml(a.color || '')}</div>
    <div class="tags">${(a.tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join('')}</div>
    <div class="ai-notes">${escHtml(a.notes || '')}</div>
  `;
  card.scrollIntoView({ behavior: 'smooth' });
}

// ── 图库 ─────────────────────────────────────────────────
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    galleryStatus = btn.dataset.status;
    loadGallery(true);
  });
});

async function loadGallery(reset = false) {
  if (reset) {
    galleryOffset = 0;
    document.getElementById('gallery').innerHTML = '';
  }

  const url = `${API}/api/images?limit=20&offset=${galleryOffset}${galleryStatus ? '&status=' + galleryStatus : ''}`;
  const data = await fetch(url).then(r => r.json());
  galleryTotal = data.total;

  const grid = document.getElementById('gallery');
  const empty = document.getElementById('galleryEmpty');
  const loadMore = document.getElementById('loadMoreBtn');

  if (data.items.length === 0 && galleryOffset === 0) {
    empty.classList.remove('hidden');
    loadMore.classList.add('hidden');
    return;
  }
  empty.classList.add('hidden');

  data.items.forEach(img => grid.appendChild(makeGalleryItem(img)));
  galleryOffset += data.items.length;

  if (galleryOffset < galleryTotal) {
    loadMore.classList.remove('hidden');
    loadMore.onclick = () => loadGallery(false);
  } else {
    loadMore.classList.add('hidden');
  }
}

function makeGalleryItem(img) {
  const el = document.createElement('div');
  el.className = 'gallery-item' + (selectMode ? ' selectable' : '');
  el.dataset.id = img.id;
  const s = STATUS_MAP[img.status] || STATUS_MAP.pending;
  const tags = (img.ai_tags || []).slice(0, 2).join(' · ');
  el.innerHTML = `
    <img src="/uploads/${escHtml(img.filename)}" alt="" loading="lazy">
    <span class="select-check"></span>
    <span class="status-badge ${s.cls}">${s.label}</span>
    <div class="gallery-item-info">
      <div class="gallery-item-style">${escHtml(img.ai_style || '—')}</div>
      <div class="gallery-item-meta">${escHtml(tags || img.source_platform || '')}</div>
    </div>`;
  el.addEventListener('click', () => {
    if (!selectMode) openModal(img);
  });
  return el;
}

// ── 详情弹窗 ─────────────────────────────────────────────
const modal      = document.getElementById('modal');
const modalImg   = document.getElementById('modalImg');
const modalBody  = document.getElementById('modalBody');
const modalClose = document.getElementById('modalClose');

document.getElementById('modalBackdrop').addEventListener('click', closeModal);
modalClose.addEventListener('click', closeModal);

function closeModal() {
  modal.classList.add('hidden');
  currentModal = null;
}

function openModal(img) {
  currentModal = img.id;
  modalImg.src = `/uploads/${img.filename}`;
  renderModalBody(img);
  modal.classList.remove('hidden');
}

function renderModalBody(img) {
  const s = STATUS_MAP[img.status] || STATUS_MAP.pending;
  const tags = (img.ai_tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join('');

  modalBody.innerHTML = `
    <div class="ai-style">${escHtml(img.ai_style || '—')}</div>
    <div class="ai-meta">${escHtml(img.ai_category || '')}  ${escHtml(img.ai_color || '')}  ·  ${escHtml(img.source_platform || '')}</div>
    <div class="tags">${tags}</div>
    <div class="ai-notes">${escHtml(img.ai_notes || '')}</div>

    <div class="section-title">审核状态</div>
    <div class="status-buttons">
      <button class="status-btn ${img.status === 'pending'  ? 'active-pending'  : ''}" data-s="pending">⏳ 待审核</button>
      <button class="status-btn ${img.status === 'sent'     ? 'active-sent'     : ''}" data-s="sent">📨 已发老板娘</button>
      <button class="status-btn ${img.status === 'approved' ? 'active-approved' : ''}" data-s="approved">✅ 通过</button>
      <button class="status-btn ${img.status === 'rejected' ? 'active-rejected' : ''}" data-s="rejected">❌ 拒绝</button>
    </div>

    <div class="section-title">备注</div>
    <textarea class="notes-area" rows="3" placeholder="记点什么...">${escHtml(img.user_notes || '')}</textarea>
    <button class="save-notes-btn">保存备注</button>
    <button class="delete-btn">删除这张图</button>
  `;

  // 状态按钮
  modalBody.querySelectorAll('.status-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`${API}/api/images/${img.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: btn.dataset.s }),
      });
      img.status = btn.dataset.s;
      renderModalBody(img);
      refreshGalleryItem(img);
      loadStats();
    });
  });

  // 保存备注
  modalBody.querySelector('.save-notes-btn').addEventListener('click', async () => {
    const notes = modalBody.querySelector('.notes-area').value;
    await fetch(`${API}/api/images/${img.id}/notes`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    img.user_notes = notes;
    showToast('备注已保存');
  });

  // 删除
  modalBody.querySelector('.delete-btn').addEventListener('click', async () => {
    if (!confirm('确认删除这张图？')) return;
    await fetch(`${API}/api/images/${img.id}`, { method: 'DELETE' });
    closeModal();
    loadGallery(true);
    loadStats();
  });
}

// 刷新图库里对应的卡片状态
function refreshGalleryItem(img) {
  loadGallery(true);
}

// 上传完成后立刻把新图插到图库最前面
function prependToGallery(img) {
  const grid = document.getElementById('gallery');
  document.getElementById('galleryEmpty').classList.add('hidden');
  // 如果有筛选且不是"全部"，新图是 pending 状态，只在全部/pending 时插入
  if (galleryStatus === '' || galleryStatus === 'pending') {
    grid.prepend(makeGalleryItem(img));
    galleryOffset += 1;
  }
}

// ── 工具函数 ─────────────────────────────────────────────
function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function showToast(msg) {
  const t = document.createElement('div');
  t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:20px;font-size:14px;z-index:999;';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2000);
}

// ── 批量多选删除 ─────────────────────────────────────────
let selectMode = false;
const selectedIds = new Set();

const selectModeBtn  = document.getElementById('selectModeBtn');
const batchBar       = document.getElementById('batchBar');
const batchCountEl   = document.getElementById('batchCount');
const batchDeleteBtn = document.getElementById('batchDelete');
const batchCancelBtn = document.getElementById('batchCancel');
const batchSelectAll = document.getElementById('batchSelectAll');

selectModeBtn.addEventListener('click', () => {
  selectMode ? exitSelectMode() : enterSelectMode();
});

function enterSelectMode() {
  selectMode = true;
  selectedIds.clear();
  selectModeBtn.classList.add('active');
  selectModeBtn.textContent = '退出';
  batchBar.classList.remove('hidden');
  updateBatchBar();
  // 给所有图片卡片加 selectable 样式
  document.querySelectorAll('.gallery-item').forEach(el => {
    el.classList.add('selectable');
    el.classList.remove('selected');
  });
}

function exitSelectMode() {
  selectMode = false;
  selectedIds.clear();
  selectModeBtn.classList.remove('active');
  selectModeBtn.textContent = '多选';
  batchBar.classList.add('hidden');
  document.querySelectorAll('.gallery-item').forEach(el => {
    el.classList.remove('selectable', 'selected');
  });
}

function updateBatchBar() {
  const n = selectedIds.size;
  batchCountEl.textContent = `已选 ${n} 张`;
  batchDeleteBtn.disabled = n === 0;
  batchSelectAll.textContent =
    document.querySelectorAll('.gallery-item.selected').length === document.querySelectorAll('.gallery-item').length
      ? '取消全选' : '全选';
}

// 全选 / 取消全选
batchSelectAll.addEventListener('click', () => {
  const items = document.querySelectorAll('.gallery-item');
  const allSelected = [...items].every(el => el.classList.contains('selected'));
  items.forEach(el => {
    const id = Number(el.dataset.id);
    if (allSelected) {
      el.classList.remove('selected');
      selectedIds.delete(id);
    } else {
      el.classList.add('selected');
      el.querySelector('.select-check').textContent = '✓';
      selectedIds.add(id);
    }
  });
  updateBatchBar();
});

batchCancelBtn.addEventListener('click', exitSelectMode);

batchDeleteBtn.addEventListener('click', async () => {
  const n = selectedIds.size;
  if (n === 0) return;
  if (!confirm(`确认删除选中的 ${n} 张图片？此操作不可恢复。`)) return;

  await fetch(`${API}/api/images/batch`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: [...selectedIds] }),
  });

  showToast(`已删除 ${n} 张`);
  exitSelectMode();
  loadGallery(true);
  loadStats();
});

// makeGalleryItem 需要支持多选点击，重新封装点击逻辑
// 在原有 makeGalleryItem 基础上，进入多选模式后拦截点击
const _origMakeGalleryItem = makeGalleryItem;
// 直接改 gallery 的事件委托更干净
document.getElementById('gallery').addEventListener('click', e => {
  if (!selectMode) return;
  const item = e.target.closest('.gallery-item');
  if (!item) return;
  e.stopPropagation();
  const id = Number(item.dataset.id);
  if (item.classList.contains('selected')) {
    item.classList.remove('selected');
    item.querySelector('.select-check').textContent = '';
    selectedIds.delete(id);
  } else {
    item.classList.add('selected');
    item.querySelector('.select-check').textContent = '✓';
    selectedIds.add(id);
  }
  updateBatchBar();
}, true);  // 捕获阶段拦截，阻止打开详情
