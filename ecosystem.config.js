module.exports = {
  apps: [
    {
      name: 'voice-agent-api',
      cwd: '/root/tmt-navi-dev/auto-calling-api-by-voice',
      script: 'run.py',
      interpreter: '/root/tmt-navi-dev/auto-calling-api-by-voice/venv/bin/python',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/root/tmt-navi-dev/auto-calling-api-by-voice',
      },
    },
  ],
};
