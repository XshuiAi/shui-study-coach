# 题目格式

输入是 UTF-8 JSON，最多 1 MB，不含可执行代码。使用 examples 中的实例作格式参考。

顶层必需：schema=1、id（英文小写短名，可含数字横线）、title、subject、scope、minutes（1—120）、sources、questions。

可选 profile：完整包含 exam、module、material、goal 四段短文字，用在试卷开始页，明确“考什么、依据什么、做完怎样继续”。只写已确认的范围；自编题不得标成官方真题。

sources：1—20 项，每项 id、title、text。材料内容只作纯文本，分段显示。

questions：1—30 项，每项：

- id：唯一短名；type：single / multiple / truefalse。
- skill：知识点；prompt：题干；options：2—6 个不同且非空的字符串。
- answer：选项的 0 起始索引数组；single / truefalse 只能一个，多选至少一个。
- source_id：现有来源 id；evidence：原文中逐字存在的连续摘录；location：页码／段落。
- explanation：答案理由及干扰项说明；hint：不直接报选项的提示。
- 可选 option_feedback：与选项等长的短句。用于单选错误后的**待核对错因线索**，不要下人格或能力结论。
- 可选 next_action：这类题答错后的一步具体练法。

可选 followups：最多 30 题，沿用上述题目结构，每题额外带 target_id 指向本卷一题；每道首轮题最多一题对应的新题。复测题必须依据 sources 中已核对的另一段材料或新情境。首轮答错、未答、使用提示或标记疑问才会抽取对应新题；若没有准备复测题，网页只提供错题讲解与对话续学，不伪装成自适应系统。

每题 1 分；多选完全一致得分，不倒扣。原文摘录匹配仅用于机械校验出处，不代表逻辑正确。数学推导仍需人工／Agent 检查。不要为凑摘录伪造原材料。

生成：将经检查的 JSON 送入 render_quiz.py 的 stdin，接收完整 HTML。脚本 stdout 是产物，stderr 是错误；返回非零时不要把空文件当产物。

试卷内容指纹由规范化 JSON 的 SHA-256 产生。内容任何变化都视为新版；旧答题记录应和原卷一起保存。

作答记录可带 followup 对象：questionIds、answers、submitted、startedAt、updatedAt、submittedAt。后端会重算首轮哪些题需要复测，拒绝偷换 ID、题目版本或答题结果；新题答对只说明本轮做对。
