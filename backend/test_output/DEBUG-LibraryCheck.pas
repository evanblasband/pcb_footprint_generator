{ Debug script to check PCB Library detection }
{ Run this to see what Altium sees }

Procedure CheckLibrary;
Var
    Board      : IPCB_Board;
    CurrentLib : IPCB_Library;
    Msg        : String;
Begin
    Msg := 'Library Detection Debug:' + #13#10 + #13#10;

    // Check PCBServer
    If PCBServer = Nil Then
    Begin
        ShowMessage('ERROR: PCBServer is Nil - scripting system not initialized');
        Exit;
    End;
    Msg := Msg + '1. PCBServer: OK' + #13#10;

    // Try GetCurrentPCBBoard
    Board := PCBServer.GetCurrentPCBBoard;
    If Board = Nil Then
        Msg := Msg + '2. GetCurrentPCBBoard: Nil (no PCB document)' + #13#10
    Else
    Begin
        Msg := Msg + '2. GetCurrentPCBBoard: Found a document' + #13#10;
        If Board.IsLibrary Then
            Msg := Msg + '   -> Board.IsLibrary: TRUE (this IS a library)' + #13#10
        Else
            Msg := Msg + '   -> Board.IsLibrary: FALSE (this is a PCB, not library)' + #13#10;
    End;

    // Try GetCurrentPCBLibrary
    CurrentLib := PCBServer.GetCurrentPCBLibrary;
    If CurrentLib = Nil Then
        Msg := Msg + '3. GetCurrentPCBLibrary: Nil' + #13#10
    Else
    Begin
        Msg := Msg + '3. GetCurrentPCBLibrary: Found library!' + #13#10;
        Msg := Msg + '   -> Library has Board: ';
        If CurrentLib.Board <> Nil Then
            Msg := Msg + 'Yes' + #13#10
        Else
            Msg := Msg + 'No' + #13#10;
    End;

    Msg := Msg + #13#10 + 'Make sure:' + #13#10;
    Msg := Msg + '- A .PcbLib file is open (not .PrjPCB or .PcbDoc)' + #13#10;
    Msg := Msg + '- The library tab is the active/focused tab' + #13#10;
    Msg := Msg + '- Try clicking inside the library editor area first';

    ShowMessage(Msg);
End;

Procedure Run;
Begin
    CheckLibrary;
End;
