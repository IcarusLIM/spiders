# 字体加密破解

> 参考博客：https://blog.csdn.net/jerrism/article/details/105755042

## 背景

[猫眼](https://www.maoyan.com/films/1413641)的票房数据在网页源码中是不对应任何有效文字的Unicode编码，同过动态加载的字体渲染成人可以识别的“字”（本质是字体文件定义的，Unicode映射成的像字的形状），故无法直接抓取

要加载的字体文件是每次访问页面时动态生成的，即Unicode和字形的对应关系是变化的；同时不同的字体文件中，表示同一个字的字形有轻微扰动，不能直接根据字形的锚点坐标判等

## 解决方案

整体思路为：

- 首先标注一份字体文件作为基准，记录每个字形所对应的文字  
- 对每个抓取到的页面，下载其字体文件，提取页面中表示票房的Unicode编码并在字体文件中找到对应的字形  
- 将字形与基准文件中的字形逐个比对，找到最相似的，结合基准文件字形和文字对应关系即可翻译成有效数字

受扰动影响不能直接判等，所以将字形的锚点的n个坐标值视为2n维向量，使用余弦相似性计算最佳匹配

## 代码及使用

准备工作：

首先下载字体（@font-face中stonefont字体，保存.woff文件）保存为`maoyan.woff`  
运行`FontDecrypter.show_glyphs`方法，此方法接收一个字体文件，打印字体文件定义的Unicode列表，并将每个Unicode对应的字形渲染到图片保存到`font.png`  
参照输出的Unicode列表和`font.png`编辑对应文件`maoyan.json`  

使用：

创建`FontDecrypter`，将字体文件`maoyan.woff`和对应关系`maoyan.json`传入  
使用`sub_all`方法将Unicode转化为有效字符，入参为新的html包含的字体文件和加密Unicode
