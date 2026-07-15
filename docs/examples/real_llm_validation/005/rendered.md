The minor of an element \(a_{ij}\) in a determinant is the determinant you obtain after removing the \(i\)‑th row and the \(j\)‑th column that contain \(a_{ij}\). This minor is written as \(M_{ij}\). [Minors and Cofactors] concept=concept.4407c78c6540 field=definition_texts locator=0  

Theorem 1 follows from these definitions. [Minors and Cofactors] concept=concept.4407c78c6540 field=definition_texts locator=1 [Minors and Cofactors] concept=concept.4407c78c6540 field=definition_texts locator=2 [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=7b1519b37d6a6e0a object=theorem:7b1519b37d6a6e0a

**Step 1.** Identify the element whose minor you need. In the determinant  

\[
\begin{matrix}
7 & 8 & 9\\
\end{matrix}
\]

the element 6 is located in the second row and third column. [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=0  

**Step 2.** Delete the row and column containing that element. Removing row 2 and column 3 leaves the sub‑matrix  

\[
\begin{matrix}
1 & 2\\
7 & 8
\end{matrix}
\] [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=1  

**Step 3.** Compute the determinant of the sub‑matrix:  

\[
M_{23}= (1)(8) - (2)(7) = 8 - 14 = -6. \] [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=2  

**Step 4.** Recall the definition of a cofactor:  

\[
A_{ij}=(-1)^{i+j}\,M_{ij}, 
\]  

where \(M_{ij}\) is the minor of the element \(a_{ij}\). [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=3  

---

**Step 5.** For a new determinant  

\[
\begin{matrix}
1 & 2\\
3 & 4
\end{matrix}
\]  

find the minors of each element. [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=4  

**Step 6.** The minor of \(a_{11}=1\) is the determinant of the sub‑matrix obtained by deleting row 1 and column 1:  

\[
M_{11}=3. \] [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=5  

**Step 7.** The minor of \(a_{12}=2\) is  

\[
M_{12}=4. \] [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=6  

**Step 8.** The minor of \(a_{21}=3\) is  

\[
M_{21}=-2. \] [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=7  

**Step 9.** The minor of \(a_{22}=4\) is  

\[
M_{22}=1. \] [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=8  

**Step 10.** Compute the cofactors using \(A_{ij}=(-1)^{i+j}M_{ij}\).  

- \(A_{11}=(-1)^{1+1}M_{11}=3\). [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=9  
- \(A_{12}=(-1)^{1+2}M_{12}= -4\). [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=10  
- \(A_{21}=(-1)^{2+1}M_{21}= 2\). [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=11  
- \(A_{22}=(-1)^{2+2}M_{22}= 1\). [Minors and Cofactors] concept=concept.4407c78c6540 field=example_texts locator=12  

1. Write the minors and cofactors of the elements of the following determinants:  
   (i) \(\begin{bmatrix}2 & 4 \\ 0 & 3\end{bmatrix}\) – (ii) \(\begin{bmatrix}a & c \\ b & d\end{bmatrix}\) [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=31449ce5b3d923b4 object=exercise:31449ce5b3d923b4  

2. Write the minors and cofactors of the elements of the following determinants:  
   (i) \(\begin{bmatrix}0 & 1 \\ 5 & 3\end{bmatrix}\) – (ii) \(\begin{bmatrix}0 & 1 & 2 \\ 5 & 3 & 8 \\ 2 & 0 & 1\end{bmatrix}\) [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=6d485195f9e49ae7 object=exercise_question:6d485195f9e49ae7  

3. Using the cofactors of the elements of the second row, evaluate \(\Delta =\begin{bmatrix}1 & 2 & 3 \\ x & y & z \\ y & z & x\end{bmatrix}\) [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=f4b39bc7ac66114f object=exercise_question:f4b39bc7ac66114f  

4. Using the cofactors of the elements of the third column, evaluate \(\Delta =\begin{bmatrix}z & x & y \\ 1 & 1 & 1 \\ 1 & 2 & 3\end{bmatrix}\) [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=a1b1f68a622f1e25 object=exercise_question:a1b1f68a622f1e25  

5. If \(\Delta =\begin{bmatrix}21 & 22 & 23 \\ 31 & 32 & 33\end{bmatrix}\) and \(A_{ij}\) is the cofactor of \(a_{ij}\), which of the following gives the value of \(\Delta\)?  
   (A) \(a_{11}A_{31}+a_{12}A_{32}+a_{13}A_{33}\)  
   (B) \(a_{11}A_{11}+a_{12}A_{21}+a_{13}A_{31}\)  
   (C) \(a_{21}A_{11}+a_{22}A_{12}+a_{23}A_{13}\)  
   (D) \(a_{11}A_{11}+a_{21}A_{21}+a_{31}A_{31}\) [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=aa10255b87f0a340 object=exercise_question:aa10255b87f0a340  

6. **Adjoint of a matrix** – The adjoint of a square matrix \(A=[a_{ij}]_{n\times n}\) is defined as the transpose of the matrix \([A_{ij}]_{n\times n}\), where \(A_{ij}\) is the cofactor of the element \(a_{ij}\). The adjoint is denoted by \(\operatorname{adj}A\). [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=cdb354999cad9d50 object=exercise_question:cdb354999cad9d50  

7. For the matrix  
   \[
   A=\begin{bmatrix}
   11 & 12 & 13\\
   21 & 22 & 23\\
   31 & 32 & 33
   \end{bmatrix},
   \]  
   write its adjoint explicitly (show the transpose of the cofactor matrix). [Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=e2a9af82662dd54d object=exercise_question:e2a9af82662dd54d  

---  

Citations:  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=31449ce5b3d923b4 object=exercise:31449ce5b3d923b4  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=6d485195f9e49ae7 object=exercise_question:6d485195f9e49ae7  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=f4b39bc7ac66114f object=exercise_question:f4b39bc7ac66114f  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=a1b1f68a622f1e25 object=exercise_question:a1b1f68a622f1e25  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=aa10255b87f0a340 object=exercise_question:aa10255b87f0a340  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=cdb354999cad9d50 object=exercise_question:cdb354999cad9d50  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=e2a9af82662dd54d object=exercise_question:e2a9af82662dd54d  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=d0f06f2fab5d65a5 object=exercise_question:d0f06f2fab5d65a5  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=fe164dedc8679b4d object=exercise_question:fe164dedc8679b4d  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=606a7a660f19ddca object=exercise_question:606a7a660f19ddca  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=106fb870dc620409 object=exercise_question:106fb870dc620409  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=3def84b14221ed3f object=exercise_question:3def84b14221ed3f  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=bf6151ae4297558d object=exercise_question:bf6151ae4297558d  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=3a19504477ee04ab object=exercise_question:3a19504477ee04ab  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=cffb5ab546740bcc object=exercise_question:cffb5ab546740bcc  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=462d33fc7a4057d3 object=exercise_question:462d33fc7a4057d3  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=c2688ed3ebcaa660 object=exercise_question:c2688ed3ebcaa660  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=d6d3ff46908ba223 object=exercise_question:d6d3ff46908ba223  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=676aeb74a8545530 object=exercise_question:676aeb74a8545530  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=aaf94e28dbaad548 object=exercise_question:aaf94e28dbaad548  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=e0906e5075ce2155 object=exercise_question:e0906e5075ce2155  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=70b02309536b85f8 object=exercise_question:70b02309536b85f8  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=a12eb8505221c2ee object=exercise_question:a12eb8505221c2ee  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=a6d7d05449cc3640 object=exercise_question:a6d7d05449cc3640  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=950b018c21e0b7d0 object=exercise_question:950b018c21e0b7d0  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=f163e392945dddf9 object=exercise_question:f163e392945dddf9  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=6e29127a00797126 object=exercise_question:6e29127a00797126  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=a9b7bbf9403c54ea object=exercise_question:a9b7bbf9403c54ea  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=43a42b80e52cf5f7 object=exercise_question:43a42b80e52cf5f7  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=c6ead09a8a765977 object=exercise_question:c6ead09a8a765977  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=292032757b2c96b5 object=exercise_question:292032757b2c96b5  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=915f342a4360a1dc object=exercise_question:915f342a4360a1dc  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=c5080b6e891f6fb9 object=exercise_question:c5080b6e891f6fb9  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=e32a970eed3588cc object=exercise_question:e32a970eed3588cc  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=99f11202ae373280 object=exercise_question:99f11202ae373280  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=eb4248f8ae776a2f object=exercise_question:eb4248f8ae776a2f  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=06f5148c2ea0deec object=exercise_question:06f5148c2ea0deec  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=8ba941ea0045f1ab object=exercise_question:8ba941ea0045f1ab  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=5df0d6371e60045a object=exercise_question:5df0d6371e60045a  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=58cb8d5692913bcc object=exercise_question:58cb8d5692913bcc  
[Minors and Cofactors] concept=concept.4407c78c6540 field=ir_object locator=2862453e5d74e4a5 object=exercise_question:2862453e5d74e4a5

The subject of minors and cofactors is presented at a medium level of difficulty. For further information, refer to [Minors and Cofactors] concept=concept.4407c78c6540 field=concept locator=concept.4407c78c6540.