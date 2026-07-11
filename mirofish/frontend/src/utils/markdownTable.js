const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#039;')

const splitRow = (line) => line
  .trim()
  .replace(/^\||\|$/g, '')
  .split(/(?<!\\)\|/)
  .map(cell => escapeHtml(cell.trim().replace(/\\\|/g, '|')).replace(/&lt;br\s*\/?&gt;/gi, '<br>'))

const isSeparator = (line) => {
  const cells = line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim())
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell))
}

export const renderMarkdownTables = (content) => {
  const lines = content.split(/\r?\n/)
  const output = []
  let inCodeFence = false
  for (let index = 0; index < lines.length; index++) {
    if (lines[index].trim().startsWith('```')) {
      inCodeFence = !inCodeFence
      output.push(lines[index])
      continue
    }
    if (inCodeFence) {
      output.push(lines[index])
      continue
    }
    if (!lines[index].includes('|') || index + 1 >= lines.length || !isSeparator(lines[index + 1])) {
      output.push(lines[index])
      continue
    }

    const headers = splitRow(lines[index])
    const separators = splitRow(lines[index + 1])
    if (headers.length !== separators.length) {
      output.push(lines[index])
      continue
    }

    const rows = []
    index += 2
    while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
      rows.push(splitRow(lines[index]))
      index++
    }
    index--

    const header = headers.map(cell => `<th>${cell}</th>`).join('')
    const body = rows
      .map(row => `<tr>${headers.map((_, cellIndex) => `<td>${row[cellIndex] || ''}</td>`).join('')}</tr>`)
      .join('')
    output.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`)
  }
  return output.join('\n')
}
