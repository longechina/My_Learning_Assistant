# Notes Upload Rules

1. 文件命名规则：
   - 关联课程笔记: 课程_章节_序号.扩展名
     例: chinese_ch_01_01.md
   - 独立笔记: independent_序号.扩展名
     例: independent_001.pdf
   - AI 实时笔记: session_YYYYMMDD_HHMMSS/序号.扩展名
     例: session_20260405_1530/001.md

2. 支持的文件类型：
   - 文本: md, txt
   - 富文本: docx, pdf
   - 表格: xlsx
   - 图片: jpg, png, gif
   - 音频: mp3, wav
   - 视频: mp4, mov, webm

3. 上传校验：
   - 必须符合命名规则
   - 关联笔记必须指定课程和章节
   - 文件类型必须受支持

4. 搜索与索引：
   - notes_index.json 会索引所有笔记的课程、章节、标签、日期、文件名
   - 用于 UI 快速搜索和自动加载
