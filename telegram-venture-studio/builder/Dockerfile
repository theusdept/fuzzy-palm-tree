FROM oven/bun:1.2.23-alpine
WORKDIR /app
COPY index.ts ./index.ts
USER bun
ENV PORT=3000
EXPOSE 3000
CMD ["bun", "run", "index.ts"]
