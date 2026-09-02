# PatraRekha Phase 3 + 4 UI layer

This phase adds reusable UI pieces for the Documents and AI Chat experiences.

## Documents

Use `DocumentCard` for document tiles/list rows:

```jsx
import { DocumentCard } from "@/components/ui";

<DocumentCard
  name={document.name}
  type="PDF"
  meta={`${document.pages ?? ""} pages`}
  status={document.status === "processing" ? "processing" : "indexed"}
  onClick={() => openDocument(document)}
  onAction={() => openDocumentMenu(document)}
/>
```

For upload/indexing states:

```jsx
import { ProcessingPipeline } from "@/components/ui";

<ProcessingPipeline active="embed" />
```

Recommended state mapping:
- upload -> `upload`
- text extraction/OCR -> `extract`
- NER/date extraction -> `entities`
- summarization -> `summarize`
- embeddings -> `embed`
- Pinecone/indexing -> `index`

## Chat

Use `AIThinking` while the request is being processed:

```jsx
import { AIThinking } from "@/components/ui";

<AIThinking stage="Searching your documents..." />
```

Then update the stage as your existing backend progresses, e.g.
`Finding relevant passages...` -> `Synthesizing answer...`.

For citations/sources:

```jsx
import { SourceList } from "@/components/ui";

<SourceList
  sources={sources.map((source) => ({
    id: source.id,
    title: source.name,
    meta: source.page ? `Page ${source.page}` : source.meta,
    excerpt: source.excerpt,
  }))}
/>
```

Important: these components intentionally do not assume your API response schema. Wire them to the existing state/handlers in `documents.jsx` and `chatpdf.jsx` rather than replacing backend logic.

## UX direction

Documents:
- cards should lift subtly on hover
- actions should appear on hover/focus
- processing should show actual pipeline progress
- loading should use skeletons instead of a blank screen
- search/filter results should enter with small staggered motion

Chat:
- show a short processing state instead of a frozen UI
- animate the answer container in once available
- make sources expandable
- keep animation restrained so the interface still feels institutional/enterprise

All components use the existing `motion/react` dependency.
