# GitHub Actions Deploy Example (Docker Compose)

```yaml
name: Deploy
on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up SSH
        uses: webfactory/ssh-agent@v0.8.0
        with:
          ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
      - name: Copy files to server
        run: |
          rsync -avz --delete docker-compose.postgres.yml ${{ secrets.REMOTE_USER }}@${{ secrets.REMOTE_HOST }}:/opt/gas/
      - name: Deploy via SSH
        run: |
          ssh -o StrictHostKeyChecking=no ${{ secrets.REMOTE_USER }}@${{ secrets.REMOTE_HOST }} << 'EOF'
          set -e
          cd /opt/gas
          docker compose -f docker-compose.postgres.yml pull
          docker compose -f docker-compose.postgres.yml up -d
          docker compose -f docker-compose.postgres.yml ps
          EOF
```

