C SUBROUTINE SHERR (IERR,MESS,LMESS)                                   
C                                                                       
C PURPOSE        To print an error number and an error message  
C                or just an error message.                      
C                                                                       
C USAGE          CALL SHERR (IERR,MESS,LMESS)                  
C                                                                       
C ARGUMENTS                                                             
C ON INPUT       IERR                                           
C                  The error number (printed only if non-zero). 
C                                                               
C                MESS                                           
C                  Message to be printed.                       
C                                                               
C                LMESS                                          
C                  Number of characters in mess (.LE. 130).     
C                                                                       
C ARGUMENTS                                                             
C ON OUTPUT      None                                           
C                                                                       
C I/O            The message is writen to unit 6.             
C
C ******************************************************************    
C
      SUBROUTINE SHERR (IERR,MESS,LMESS)                               
C                                                                       
      CHARACTER *(*) MESS
C                                                                       
      IF (IERR .NE. 0) WRITE (6,'(A,I5)') ' IERR=', IERR
      WRITE (6,'(A)') MESS(1:LMESS)
C
      RETURN                                                            
      END                                                               
