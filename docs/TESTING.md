\# 电商问数项目测试记录



\## 测试目标



验证基础服务、元数据知识库、检索能力、API、LangGraph 工作流和真实问数链路。



\## 自动化测试



自动化测试不调用大模型：



```powershell

.venv\\Scripts\\python.exe -m unittest discover -s tests -v

