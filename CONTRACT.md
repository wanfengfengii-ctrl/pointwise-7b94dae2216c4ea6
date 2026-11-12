# 抓取记录候选对账：已有业务契约

资料采集链已经把多个门户和RPA导出的记录映射到同一记录ID集合。上游提供带整数代价的疑似重复候选；本仓库只做配对归并前的对账计算，每条记录最多参与一对。来源可能交叉，候选不保证二分。人工复核需要所有最优方案允许的候选，而非任意一组配对；support中的候选互不保证可以同时选择。没有网络依赖。

## 唯一业务入口

from engine import Engine
e = Engine(vertices, rows=None)
change = e.apply(rows)
result = e.read()

vertices为有限、无重复的非空字符串序列，允许空序列；初始化后固定。rows为列表，每项恰为[id,rev,u,v,cost,deleted]：id为非空字符串，rev为正整数，u/v为vertices中不同字符串，cost为任意精度整数，deleted为布尔。整数位置拒绝布尔。输入中的端点顺序属于版本内容；匹配时边无方向。候选ID与记录ID命名空间独立，不同候选ID允许连接相同端点，分别保留来源。墓碑也须满足全部字段规则。

构造时先接纳rows；之后每个ID只保留最高rev，包括墓碑。更高版本可移动两端点、改代价、撤销、复活。低版本忽略，同版本完全相同为空操作，同版本不同内容抛ValueError("REVISION_CONFLICT")。每批ID不得重复；即使版本过期也先校验字段。非法域抛ValueError("DOMAIN")，非列表批次抛ValueError("ROWS")，非法行抛ValueError("ROW")，批内重复ID抛ValueError("DUPLICATE")。逐行校验及错误先后沿用protocol.py。失败时已接纳版本与可读结果均保持批前状态；不返回部分变化。空批次合法。对象和进程内使用，无持久化要求。调用者提供的输入不得被修改；read及apply的返回值须与内部状态隔离。

## 精确结果与净变化

有效候选形成无向多重图。匹配是没有共享端点的候选ID集合；先最大化候选数，再最小化所选候选整数代价之和，负数代价合法。read返回：
{"objective":[配对数,总代价],"support":[候选ID...],"unmatched":[记录ID...]}

support恰含至少一个全局最优匹配会使用的全部候选；unmatched恰含至少一个全局最优匹配会留下的全部未配对记录。二者分别取所有最优方案的并集，不把各边可能性拼成一个方案。空图objective为[0,0]，所有记录均可能未配对。所有ID列表按Python字符串顺序排序。

apply返回：
{"before":[旧配对数,旧总代价],"after":[新配对数,新总代价],
 "add":[support净增ID...],"remove":[support净减ID...],
 "unmatched_add":[unmatched净增ID...],"unmatched_remove":[unmatched净减ID...]}
即使目标值不变，也必须报告歧义集合的变化；忽略和重放产生空净变化。read包含全部结果，不能省略孤立记录。整批修订联合形成最终状态，再计算相对批前的净变化。

samples.example为三角形ab/ac/bc代价均0，另有孤立记录：objective=[1,0]，support=["ab","ac","bc"]，unmatched=["a","b","c","isolated"]。将ab升至rev=2、代价改为-1后，objective=[1,-1]、support=["ab"]、unmatched=["c","isolated"]；remove=["ac","bc"]，unmatched_remove=["a","b"]，其余净变化为空。

## 已有正确基线与固定基准

engine.py目前直接继承正确的Reference。reference.materialize使用带缓存的精确顶点子集动态规划，遍历最优状态求support及unmatched，每批重新物化；不是生产可扩展方案。保留reference.py、protocol.py、samples.py、checks.py中的原逻辑和断言，优化实现在Engine及其新依赖中，不修改或绕过计时、内存和业务核对。

python3 checks.py normal 执行业务断言并输出NORMAL_REGRESSION_OK；包含独立候选子集穷举判定、修订、平行边、重叠奇环、大整数、冲突回滚与输入边界。
python3 checks.py demo 输出真实的三角形更正前后结果与净变化。
python3 checks.py bench 输出两种录制候选结构、24/32两个规模、六个连续修订批位的参照与Engine秒数、比率、峰值分配和增长比；正确性不符立即失败，通过输出PERFORMANCE_BASELINE_OK。bench不要求未优化基线达到优化目标。
python3 checks.py target 先执行normal，再执行相同bench并强制量化目标；未达到输出OPTIMIZATION_TARGET_MISSED且退出1，全部达到输出OPTIMIZATION_TARGET_OK且退出0。

每个批位分别计时apply，不计read和构造，三轮取中位数；同一进程交替运行Reference与Engine，逐批核对返回值和read。样本只由调用方逐批传入，禁止检查器识别、导入samples窥探后续、跨实例或全局缓存答案及利用Reference预算答案。性能测试是公开可重跑的代表负载，业务正确性与增量约束适用于任意合法有限输入，不限样本大小、端点次序或候选结构。允许改变内部表示，不要求保持Reference的缓存方法。

峰值为独立tracemalloc会话中Engine构造及随后全部批次的Python分配峰值，覆盖维护索引和返回结果。不能靠把完整计算移到read或构造、异步延后结果、外部进程或原生库隐藏开销达标；仅使用Python标准库。新增内部缓存必须随实际输入维护，不能借预读未来。原bench每类每规模每个批位的三轮中位耗时须≤同进程Reference的1/12；规模24增至32每个对应批位的中位耗时增长须≤六倍；每类每规模构造及连续修订Python分配峰值须≤64MiB。

交付优化代码和实测说明，解释如何保留奇环中的全部最优可能性，以及端点移动、撤销后的跨批求解状态更新。优化不得每批全量重建，不枚举顶点子集或匹配方案，不逐候选重求最优。允许初始化建立完整求解结构；某次修订影响全图时可沿其影响访问全图，不能无条件重建或重新求解整图。保留.pointwise-runtime.json，最终verify改为["python3","checks.py","target"]，demo沿用真实业务演示。
