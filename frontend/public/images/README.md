# Frontend static images

Put image files here. Next.js serves them from the site root.

| Folder | Use for |
|--------|---------|
| `careers/` | Talent Portal (login, careers marketing) |
| `brand/` | Logos, marks, product branding |
| `ui/` | Shared UI illustrations / empty states |

**Examples**

- File: `frontend/public/images/careers/hero.jpg`
- URL in code: `/images/careers/hero.jpg`

```tsx
<Image src="/images/careers/hero.jpg" alt="…" width={800} height={600} />
```

Keep AI orb assets under `public/ai/` (already used by Pulse).
