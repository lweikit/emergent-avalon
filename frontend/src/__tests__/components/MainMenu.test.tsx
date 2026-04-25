import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MainMenu from "../../components/MainMenu";
import api from "../../api";

jest.mock("../../api");
const mockedApi = api as jest.Mocked<typeof api>;

// Mock RuleBook to keep tests focused
jest.mock("../../components/RuleBook", () => {
  return function MockRuleBook() {
    return <div data-testid="rulebook">RuleBook</div>;
  };
});

describe("MainMenu", () => {
  const defaultProps = {
    onJoined: jest.fn(),
    onSpectate: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("rendering", () => {
    it("renders the title and subtitle", () => {
      render(<MainMenu {...defaultProps} />);
      expect(screen.getByText("Avalon")).toBeInTheDocument();
      expect(screen.getByText("The Resistance Board Game")).toBeInTheDocument();
    });

    it("renders all input fields", () => {
      render(<MainMenu {...defaultProps} />);
      expect(screen.getByPlaceholderText("Enter your name...")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Session name...")).toBeInTheDocument();
      expect(screen.getAllByPlaceholderText("Session ID...").length).toBeGreaterThanOrEqual(1);
    });

    it("renders Create Session and Join Session buttons", () => {
      render(<MainMenu {...defaultProps} />);
      expect(screen.getByText("Create Session")).toBeInTheDocument();
      expect(screen.getByText("Join Session")).toBeInTheDocument();
    });

    it("renders spectate section", () => {
      render(<MainMenu {...defaultProps} />);
      expect(screen.getByText("Spectate")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Your name (optional)")).toBeInTheDocument();
      expect(screen.getAllByPlaceholderText("Session ID...").length).toBe(2);
      expect(screen.getByText("Watch Game")).toBeInTheDocument();
    });

    it("renders the RuleBook component", () => {
      render(<MainMenu {...defaultProps} />);
      expect(screen.getByTestId("rulebook")).toBeInTheDocument();
    });
  });

  describe("form validation (disabled buttons)", () => {
    it("Create Session button is disabled when player name is empty", () => {
      render(<MainMenu {...defaultProps} />);
      const createBtn = screen.getByText("Create Session");
      expect(createBtn).toBeDisabled();
    });

    it("Create Session button is disabled when session name is empty", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Alice");

      const createBtn = screen.getByText("Create Session");
      expect(createBtn).toBeDisabled();
    });

    it("Create Session button is enabled when both fields are filled", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Alice");
      await user.type(screen.getByPlaceholderText("Session name..."), "My Game");

      const createBtn = screen.getByText("Create Session");
      expect(createBtn).toBeEnabled();
    });

    it("Join Session button is disabled when player name is empty", () => {
      render(<MainMenu {...defaultProps} />);
      const joinBtn = screen.getByText("Join Session");
      expect(joinBtn).toBeDisabled();
    });

    it("Join Session button is disabled when session ID is empty", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Alice");

      const joinBtn = screen.getByText("Join Session");
      expect(joinBtn).toBeDisabled();
    });

    it("Join Session button is enabled when name and session ID are filled", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Alice");
      // There are two "Session ID..." placeholders; get the first one (join section)
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[0], "abc123");

      const joinBtn = screen.getByText("Join Session");
      expect(joinBtn).toBeEnabled();
    });

    it("Create Session button is disabled when name is only whitespace", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "   ");
      await user.type(screen.getByPlaceholderText("Session name..."), "My Game");

      const createBtn = screen.getByText("Create Session");
      expect(createBtn).toBeDisabled();
    });

    it("Watch Game button is disabled when spectate session ID is empty", () => {
      render(<MainMenu {...defaultProps} />);
      const watchBtn = screen.getByText("Watch Game");
      expect(watchBtn).toBeDisabled();
    });

    it("Watch Game button is enabled when spectate session ID is filled", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[1], "some-id");

      const watchBtn = screen.getByText("Watch Game");
      expect(watchBtn).toBeEnabled();
    });
  });

  describe("input trimming", () => {
    it("trims whitespace from player name and session name when creating", async () => {
      mockedApi.createSession.mockResolvedValueOnce({
        data: { session_id: "s1", player_id: "p1", player_token: "t1" },
      } as any);

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "  Alice  ");
      await user.type(screen.getByPlaceholderText("Session name..."), "  My Game  ");

      await user.click(screen.getByText("Create Session"));

      await waitFor(() => {
        expect(mockedApi.createSession).toHaveBeenCalledWith("My Game", "Alice");
      });
    });

    it("trims whitespace from player name and session ID when joining", async () => {
      mockedApi.joinSession.mockResolvedValueOnce({
        data: { session_id: "s1", player_id: "p1", player_token: "t1" },
      } as any);

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "  Bob  ");
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[0], "  abc123  ");

      await user.click(screen.getByText("Join Session"));

      await waitFor(() => {
        expect(mockedApi.joinSession).toHaveBeenCalledWith("abc123", "Bob", false);
      });
    });

    it("trims spectate session ID when watching", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[1], "  watch-id  ");

      await user.click(screen.getByText("Watch Game"));

      expect(defaultProps.onSpectate).toHaveBeenCalledWith("watch-id", undefined);
    });

    it("trims spectate name and passes undefined if empty after trim", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Your name (optional)"), "   ");
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[1], "watch-id");

      await user.click(screen.getByText("Watch Game"));

      expect(defaultProps.onSpectate).toHaveBeenCalledWith("watch-id", undefined);
    });

    it("passes spectate name if non-empty after trim", async () => {
      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Your name (optional)"), " Viewer ");
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[1], "watch-id");

      await user.click(screen.getByText("Watch Game"));

      expect(defaultProps.onSpectate).toHaveBeenCalledWith("watch-id", "Viewer");
    });
  });

  describe("create session flow", () => {
    it("calls onJoined with server response data on success", async () => {
      mockedApi.createSession.mockResolvedValueOnce({
        data: { session_id: "new-session", player_id: "new-player", player_token: "new-token" },
      } as any);

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Alice");
      await user.type(screen.getByPlaceholderText("Session name..."), "My Game");
      await user.click(screen.getByText("Create Session"));

      await waitFor(() => {
        expect(defaultProps.onJoined).toHaveBeenCalledWith("new-session", "new-player", "new-token");
      });
    });

    it("displays error on create failure", async () => {
      mockedApi.createSession.mockRejectedValueOnce({
        response: { data: { detail: "Name already taken" } },
        message: "Request failed",
      });

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Alice");
      await user.type(screen.getByPlaceholderText("Session name..."), "My Game");
      await user.click(screen.getByText("Create Session"));

      await waitFor(() => {
        expect(screen.getByText(/Name already taken/)).toBeInTheDocument();
      });
    });
  });

  describe("join session flow", () => {
    it("calls onJoined using server-returned session_id", async () => {
      mockedApi.joinSession.mockResolvedValueOnce({
        data: { session_id: "resolved-uuid", player_id: "p2", player_token: "t2" },
      } as any);

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Bob");
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[0], "room-code");
      await user.click(screen.getByText("Join Session"));

      await waitFor(() => {
        // Verify it uses server-returned session_id, not the input
        expect(defaultProps.onJoined).toHaveBeenCalledWith("resolved-uuid", "p2", "t2");
      });
    });

    it("displays error on join failure", async () => {
      mockedApi.joinSession.mockRejectedValueOnce({
        response: { data: { detail: "Session not found" } },
        message: "Request failed",
      });

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Bob");
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[0], "bad-id");
      await user.click(screen.getByText("Join Session"));

      await waitFor(() => {
        expect(screen.getByText(/Session not found/)).toBeInTheDocument();
      });
    });

    it("displays generic error message when no detail", async () => {
      mockedApi.joinSession.mockRejectedValueOnce({
        message: "Network Error",
      });

      render(<MainMenu {...defaultProps} />);
      const user = userEvent.setup();
      await user.type(screen.getByPlaceholderText("Enter your name..."), "Bob");
      const sessionIdInputs = screen.getAllByPlaceholderText("Session ID...");
      await user.type(sessionIdInputs[0], "some-id");
      await user.click(screen.getByText("Join Session"));

      await waitFor(() => {
        expect(screen.getByText(/Network Error/)).toBeInTheDocument();
      });
    });
  });

  describe("spectator error", () => {
    it("displays spectatorError when provided", () => {
      render(<MainMenu {...defaultProps} spectatorError="Could not find session" />);
      expect(screen.getByText("Could not find session")).toBeInTheDocument();
    });

    it("does not display spectatorError when null", () => {
      render(<MainMenu {...defaultProps} spectatorError={null} />);
      expect(screen.queryByText("Could not find session")).not.toBeInTheDocument();
    });
  });
});
