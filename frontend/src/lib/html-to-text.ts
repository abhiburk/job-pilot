const BLOCK_TAGS = new Set([
  'ADDRESS', 'ARTICLE', 'ASIDE', 'BLOCKQUOTE', 'DIV', 'DL', 'DT', 'DD',
  'FIELDSET', 'FIGURE', 'FOOTER', 'FORM', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
  'HEADER', 'HR', 'MAIN', 'NAV', 'OL', 'P', 'PRE', 'SECTION', 'TABLE', 'TR',
  'UL',
])

const SKIPPED_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'IFRAME', 'OBJECT'])

/**
 * Converts untrusted job-description HTML to plain text.
 *
 * DOMParser produces an inert document: scripts do not run and resources
 * are not fetched. Only text content is read back, so the result is always
 * rendered as text and never as markup.
 */
export function htmlToText(input: string | null | undefined): string {
  if (!input) return ''
  if (!/<[a-z!/]/i.test(input)) return input.trim()

  const doc = new DOMParser().parseFromString(input, 'text/html')
  const parts: string[] = []

  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      parts.push((node.textContent ?? '').replace(/\s+/g, ' '))
      return
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return

    const element = node as Element
    const tag = element.tagName
    if (SKIPPED_TAGS.has(tag)) return

    if (tag === 'BR') {
      parts.push('\n')
      return
    }
    if (tag === 'LI') parts.push('\n• ')
    else if (BLOCK_TAGS.has(tag)) parts.push('\n\n')

    element.childNodes.forEach(walk)

    if (BLOCK_TAGS.has(tag)) parts.push('\n\n')
  }

  doc.body.childNodes.forEach(walk)

  return parts
    .join('')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
