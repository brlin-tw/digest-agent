if ((command.includes('rm ') || command.includes('mv ')) && command.includes('src/app.py')) {
  throw new Error('🛡️ SRE Guardian: src/app.py 是服務核心，禁止刪除或移出原路徑。');
}