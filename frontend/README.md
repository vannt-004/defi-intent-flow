This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Investor Agent

The frontend calls the backend assistant endpoint at `NEXT_PUBLIC_API_BASE_URL/assistant`. Google AI Studio keys and prompt guardrails live in the backend only.

Frontend `.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Backend `.env`:

```bash
GOOGLE_AI_STUDIO_API_KEY=your_google_ai_studio_key
GOOGLE_AI_MODEL=gemini-2.5-flash
ASSISTANT_DEFAULT_LANGUAGE=English
ASSISTANT_PROVIDER_MODE=default
```

`ASSISTANT_PROVIDER_MODE=default` uses the backend deterministic NLP router. Users can switch the assistant header to Google AI mode, or type a prompt such as `use google ai mode, explain dashboard PnL`, to call Google AI Studio for that request. Use `ASSISTANT_PROVIDER_MODE=google` to make Google AI Studio the default provider when the key is configured.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
